/*
 *
 * This file is part of Optolithium lithography modelling software.
 *
 * Copyright (C) 2015 Alexei Gladkikh
 *
 * This software is dual-licensed: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version only for NON-COMMERCIAL usage.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
 *
 * If you are interested in other licensing models, including a commercial-
 * license, please contact the author at gladkikhalexei@gmail.com
 *
 */

#include "opl_sim.h"
#include "opl_mapped_cube.h"
#include "opl_physc.h"
#include "opl_conv.h"
#include "opl_eikonal.h"
#include "opl_contours.h"
#include "opl_fft.h"

#include <thread>
#include <vector>
#include <cmath>
#include <algorithm>
#include <exception>
#include <memory>
#include <mutex>

namespace {

unsigned int machine_thread_count(void) {
	unsigned int count = std::thread::hardware_concurrency();
	if (count == 0) {
		count = 1;
	}
	return count;
}

unsigned int simulation_thread_count(size_t work_items) {
	return static_cast<unsigned int>(std::min<size_t>(machine_thread_count(), std::max<size_t>(1, work_items)));
}

unsigned int simulation_thread_count_for(size_t work_items, size_t estimated_operations) {
	return estimated_operations < 10000 ? 1 : simulation_thread_count(work_items);
}

template <typename Function>
void parallel_for(size_t work_items, unsigned int worker_count, Function function) {
	if (work_items == 0) {
		return;
	}
	worker_count = std::max(1u, worker_count);
	if (work_items < worker_count) {
		worker_count = static_cast<unsigned int>(work_items);
	}
	if (worker_count == 1) {
		for (size_t i = 0; i < work_items; ++i) {
			function(i, 0);
		}
		return;
	}

	std::vector<std::thread> workers;
	workers.reserve(worker_count);
	std::exception_ptr worker_exception;
	std::mutex exception_mutex;
	const size_t chunk_size = work_items / worker_count;
	const size_t remainder = work_items % worker_count;
	try {
		for (unsigned int worker = 0; worker < worker_count; ++worker) {
			workers.emplace_back([&, worker]() {
				const size_t begin = chunk_size * worker + std::min<size_t>(worker, remainder);
				const size_t end = begin + chunk_size + (worker < remainder ? 1 : 0);
				try {
					for (size_t i = begin; i < end; ++i) {
						function(i, worker);
					}
				} catch (...) {
					std::lock_guard<std::mutex> lock(exception_mutex);
					if (!worker_exception) {
						worker_exception = std::current_exception();
					}
				}
			});
		}
	} catch (...) {
		for (auto& worker : workers) {
			worker.join();
		}
		throw;
	}
	for (auto& worker : workers) {
		worker.join();
	}
	if (worker_exception) {
		std::rethrow_exception(worker_exception);
	}
}

SharedOpticalTransferFunction make_worker_otf(SharedOpticalTransferFunction otf) {
	ConstSharedWaferStack wafer_stack = otf->wafer_stack();
	if (!wafer_stack) {
		return otf;
	}

	// Each worker owns its reflection cache. WaferStack fills that cache lazily,
	// so sharing it across concurrent OTF evaluations would race on its maps.
	SharedWaferStack worker_stack = std::make_shared<WaferStack>(*wafer_stack);
	SharedImagingTool imaging_tool = std::const_pointer_cast<ImagingTool>(otf->imaging_tool());
	SharedExposure exposure = std::const_pointer_cast<Exposure>(otf->exposure());
	return std::make_shared<OpticalTransferFunction>(imaging_tool, exposure, worker_stack);
}

struct AerialImageWorker {
	arma::cx_mat efield;
	arma::mat intensity;
	std::unique_ptr<fft::FFT2d> transform;
	SharedOpticalTransferFunction otf;

	AerialImageWorker(uint32_t rows, uint32_t cols, int32_t fft_thread_count,
			SharedOpticalTransferFunction otf) :
		efield(rows, cols), intensity(rows, cols, arma::fill::zeros),
		transform(new fft::FFT2d(efield, fft::FFT_BACKWARD, -1, fft_thread_count)), otf(otf) { }
};

void write_aerial_image_slice(SharedResistVolume result, uint32_t s,
		const arma::mat& intensity, uint32_t n_rows, uint32_t n_cols) {
	const uint32_t midcol = n_cols / 2;
	const uint32_t midrow = n_rows / 2;
	arma::mat& layer = result->values()->slice(s);
	if (n_cols != 1 && n_rows == 1) {
		for (uint32_t c = 0; c < midcol; c++) {
			layer(0, c + midcol) = intensity(0, c);
			layer(0, c) = intensity(0, c + midcol);
		}
		layer(0, n_cols) = layer(0, 0);
	} else if (n_rows != 1 && n_cols == 1) {
		for (uint32_t r = 0; r < midrow; r++) {
			layer(r + midrow, 0) = intensity(r, 0);
			layer(r, 0) = intensity(r + midrow, 0);
		}
		layer(n_rows, 0) = layer(0, 0);
	} else if (n_rows != 1 && n_cols != 1) {
		for (uint32_t r = 0; r < midrow; r++) {
			for (uint32_t c = 0; c < midcol; c++) {
				layer(r + midrow, c + midcol) = intensity(r, c);
				layer(r, c) = intensity(r + midrow, c + midcol);
				layer(r, c + midcol) = intensity(r + midrow, c);
				layer(r + midrow, c) = intensity(r, c + midcol);

				layer(n_rows, c) = layer(0, c);
				layer(n_rows, c + midcol) = layer(0, c + midcol);
			}
			layer(r, n_cols) = layer(r, 0);
			layer(r + midrow, n_cols) = layer(r + midrow, 0);
		}
		layer(n_rows, n_cols) = layer(0, 0);
	}
}

} // namespace


SharedDiffraction diffraction(SharedImagingTool imaging_tool, SharedMask mask)
{
	LOG(INFO) << "Optolithium Core: Calculate diffraction pattern for given mask, pitch = " << mask->pitch().str();
	TIMED_FUNC(diffraction_timer);

	if (mask->is_bad()) {
		throw std::invalid_argument("Wrong mask bounding box size! "
				"Diffraction 1D can only be calculation for one-dimensional mask.");
	}

	SharedDiffraction diffraction = std::make_shared<Diffraction>(mask, imaging_tool);

	for (auto region : *mask) {
		arma::cx_double factor = region->etransmit() - mask->boundary()->etransmit();
		diffraction->add_region(region, factor);
	}

	if (!mask->is_opaque()) {
		arma::cx_double factor = mask->boundary()->etransmit();
		diffraction->values()->elem(arma::find(*diffraction->cxy() == 0.0)) += factor;
	}

	return diffraction;
}


void _calc_aerial_image(SharedResistVolume result, SharedDiffraction diffraction,
		SharedOpticalTransferFunction otf, double refractive_index, double stepxy, double stepz=0.0) {
	TIMED_FUNC(aerial_image_timer);

	const uint32_t n_rows = result->values()->n_rows != 1 ? result->values()->n_rows - 1 : result->values()->n_rows;
	const uint32_t n_cols = result->values()->n_cols != 1 ? result->values()->n_cols - 1 : result->values()->n_cols;
	const uint32_t n_slices = result->values()->n_slices;

	const uint32_t n_source_points = diffraction->source_shape->non_zeros()->n_rows;

	const double na = diffraction->numeric_aperture;

	if (n_rows != 1 && n_rows % 2 != 0) {
		throw std::invalid_argument("The result rows count must be even");
	} else if (n_cols != 1 && n_cols % 2 != 0) {
		throw std::invalid_argument("The result columns count must be even");
	}

	const bool parallel_slices = n_slices > 1 && n_slices > n_source_points;
	const size_t transform_size = static_cast<size_t>(n_rows) * n_cols;
	const size_t reflection_cache_budget = otf->wafer_stack()
			? 2 * static_cast<size_t>(8192) * 256 : 0;
	const size_t bytes_per_worker = transform_size * (sizeof(arma::cx_double) + sizeof(double)) +
			reflection_cache_budget;
	const size_t aerial_worker_budget = 256 * static_cast<size_t>(1024) * 1024;
	const size_t workers_by_memory = std::max<size_t>(1, aerial_worker_budget /
			std::max<size_t>(1, bytes_per_worker));
	const size_t work_items = parallel_slices ? n_slices : n_source_points;
	const unsigned int worker_count = static_cast<unsigned int>(std::min<size_t>(
		simulation_thread_count(work_items), workers_by_memory));
	const int32_t fft_thread_count = worker_count == 1 && transform_size >= 65536
			? static_cast<int32_t>(std::min(2u, machine_thread_count())) : 1;
	std::vector<std::unique_ptr<AerialImageWorker>> workers;
	workers.reserve(worker_count);
	for (unsigned int worker = 0; worker < worker_count; ++worker) {
		workers.emplace_back(new AerialImageWorker(n_rows, n_cols, fft_thread_count, make_worker_otf(otf)));
	}

	auto calculate_source = [&](AerialImageWorker& worker, uint32_t k, double thickness) {
		auto src_row_col = diffraction->source_shape->non_zeros()->row(k);
		const double source_irradiance = diffraction->source_shape->value(src_row_col(0), src_row_col(1));
		const double scx = na * diffraction->source_shape->cx(src_row_col(1));
		const double scy = na * diffraction->source_shape->cy(src_row_col(0));
		worker.efield.zeros();

		for (uint32_t r = 0; r < diffraction->values()->n_rows; r++) {
			for (uint32_t c = 0; c < diffraction->values()->n_cols; c++) {
				double dcy = diffraction->cy(r);
				double dcx = diffraction->cx(c);
				uint32_t e_row = (n_rows + diffraction->ky(r) - 1) % n_rows;
				uint32_t e_col = (n_cols + diffraction->kx(c) - 1) % n_cols;
				worker.efield(e_row, e_col) = worker.otf->calc(dcx - scx, dcy - scy, thickness) * diffraction->value(r, c);
			}
		}

		worker.transform->execute();
		worker.intensity += source_irradiance * arma::real(worker.efield % arma::conj(worker.efield));
	};

	if (parallel_slices) {
		parallel_for(n_slices, worker_count, [&](size_t slice_index, unsigned int worker_index) {
			const uint32_t s = static_cast<uint32_t>(slice_index);
			AerialImageWorker& worker = *workers[worker_index];
			worker.intensity.zeros();
			const double thickness = result->z(s);
			for (uint32_t k = 0; k < n_source_points; ++k) {
				calculate_source(worker, k, thickness);
			}
			worker.intensity *= (refractive_index / arma::accu(*diffraction->source_shape->values()));
			write_aerial_image_slice(result, s, worker.intensity, n_rows, n_cols);
		});
	} else {
		for (uint32_t s = 0; s < n_slices; s++) {
			const double thickness = result->z(s);
			for (const auto& worker : workers) {
				worker->intensity.zeros();
			}

			parallel_for(n_source_points, worker_count, [&](size_t source_index, unsigned int worker_index) {
				calculate_source(*workers[worker_index], static_cast<uint32_t>(source_index), thickness);
			});

			arma::mat intensity(n_rows, n_cols, arma::fill::zeros);
			for (const auto& worker : workers) {
				intensity += worker->intensity;
			}
			intensity *= (refractive_index / arma::accu(*diffraction->source_shape->values()));
			write_aerial_image_slice(result, s, intensity, n_rows, n_cols);
		}
	}
}


SharedResistVolume aerial_image(SharedDiffraction diffraction, SharedOpticalTransferFunction otf, double stepxy) {
	LOG(INFO) << "Optolithium Core: Calculate aerial image";
	double refractive_index = physc::air_nk.real();
	if (otf->wafer_stack()) {
		if (!otf->wafer_stack()->environment()) {
			throw std::invalid_argument("Environment was not specified");
		}
		double wavelength = diffraction->wavelength;
		refractive_index = otf->wafer_stack()->environment()->refraction(wavelength).real();
	}
	SharedResistVolume result = std::make_shared<ResistVolume>(diffraction->boundary, stepxy);
	_calc_aerial_image(result, diffraction, otf, refractive_index, stepxy);
	otf->imaging_tool()->flare(result);
	return result;
}


SharedResistVolume image_in_resist(SharedDiffraction diffraction,
		SharedOpticalTransferFunction otf, double stepxy, double stepz) {
	LOG(INFO) << "Optolithium Core: Calculate image in resist";
	double wavelength = diffraction->wavelength;
	if (!otf->wafer_stack()) {
		throw std::invalid_argument("Wafer stack was not specified");
	}
	if (!otf->wafer_stack()->resist()) {
		throw std::invalid_argument("Resist was not specified");
	}
	double refractive_index = otf->wafer_stack()->resist()->refraction(wavelength).real();
	double thickness = otf->wafer_stack()->resist()->thickness;
	SharedResistVolume result = std::make_shared<ResistVolume>(diffraction->boundary, thickness, stepxy, stepz);
	_calc_aerial_image(result, diffraction, otf, refractive_index, stepxy, stepz);
	otf->imaging_tool()->flare(result);
	return result;
}


SharedResistVolume latent_image(SharedResistVolume image_in_resist,
		SharedResistWaferLayer resist, SharedExposure exposure) {
	LOG(INFO) << "Optolithium Core: Calculate exposed latent image";
	TIMED_FUNC(latent_image_timer);
	const arma::cube& values = *image_in_resist->values();
	// Create new resist volume object with same dimensions without copying data from it.
	SharedResistVolume result = std::make_shared<ResistVolume>(*image_in_resist, true);

	const double factor = -exposure->dose() * resist->exposure->c;
	const size_t total_elem = values.n_elem;
	const double* in_ptr = values.memptr();
	double* out_ptr = result->values()->memptr();
	parallel_for(total_elem, simulation_thread_count_for(total_elem, total_elem), [&](size_t i, unsigned int) {
		out_ptr[i] = std::exp(factor * in_ptr[i]);
	});

	return result;
}


SharedResistVolume peb_latent_image(SharedResistVolume latent_image,
		SharedResistWaferLayer resist, SharedPostExposureBake peb) {
	LOG(INFO) << "Optolithium Core: Calculate PEB latent image";
	// The convolution overwrites every output voxel, so do not copy the input cube.
	SharedResistVolume result = std::make_shared<ResistVolume>(*latent_image, true);

	arma::vec kernelx = resist->peb->kernel(peb, latent_image->stepx());
	arma::vec kernely = resist->peb->kernel(peb, latent_image->stepy());
	arma::vec kernelz = resist->peb->kernel(peb, latent_image->stepz());

	// Perform separable convolution

	const arma::cube& input = *latent_image->values();
	arma::cube& output = *result->values();

	const size_t row_count = static_cast<size_t>(input.n_slices) * input.n_rows;
	const size_t row_operations = row_count * input.n_cols * kernelx.n_elem;
	parallel_for(row_count, simulation_thread_count_for(row_count, row_operations), [&](size_t index, unsigned int) {
		const uint32_t s = static_cast<uint32_t>(index / input.n_rows);
		const uint32_t r = static_cast<uint32_t>(index % input.n_rows);
		const arma::rowvec row = input.slice(s).row(r);
		output.slice(s).row(r) = conv::conv1d(row, kernelx, conv::CIRCULAR);
	});

	const size_t column_count = static_cast<size_t>(input.n_slices) * input.n_cols;
	const size_t column_operations = column_count * input.n_rows * kernely.n_elem;
	parallel_for(column_count, simulation_thread_count_for(column_count, column_operations), [&](size_t index, unsigned int) {
		const uint32_t s = static_cast<uint32_t>(index / input.n_cols);
		const uint32_t c = static_cast<uint32_t>(index % input.n_cols);
		const arma::colvec col = output.slice(s).col(c);
		output.slice(s).col(c) = conv::conv1d(col, kernely, conv::CIRCULAR);
	});

	const size_t tube_count = static_cast<size_t>(input.n_rows) * input.n_cols;
	const size_t tube_operations = tube_count * input.n_slices * kernelz.n_elem;
	parallel_for(tube_count, simulation_thread_count_for(tube_count, tube_operations), [&](size_t index, unsigned int) {
		const uint32_t r = static_cast<uint32_t>(index / input.n_cols);
		const uint32_t c = static_cast<uint32_t>(index % input.n_cols);
		const arma::cube tube = output.tube(r, c);
		output.tube(r, c) = conv::conv1d(tube, kernelz, conv::SYMMETRIC);
	});

	return result;
}


//#define ENABLE_DEBUG_RATES


SharedResistVolume develop_time_contours(SharedResistVolume peb_latent_image, SharedResistWaferLayer resist) {
	LOG(INFO) << "Optolithium Core: Calculate develop time contours";
	// This volume is initialized completely below; copying the input cube is wasteful.
	SharedResistVolume result = std::make_shared<ResistVolume>(*peb_latent_image, true);

	const arma::cube& values = *peb_latent_image->values();

	std::shared_ptr<arma::cube> rates_storage = storage::make_cube(
		values.n_rows, values.n_cols, values.n_slices);
	arma::cube& rates = *rates_storage;

//	LOG(INFO) << "Calculate development rates";
	const size_t plane_size = static_cast<size_t>(rates.n_rows) * rates.n_cols;
	parallel_for(rates.n_elem, simulation_thread_count_for(rates.n_elem, rates.n_elem), [&](size_t index, unsigned int) {
		const size_t s = index / plane_size;
		const double depth = peb_latent_image->z(static_cast<uint32_t>(s));
		rates[index] = resist->rate->calculate(values[index], depth);
	});

#ifndef ENABLE_DEBUG_RATES
	arma::cube& develop = *result->values();

//	LOG(INFO) << "Create initial resist profile contour";
	develop.fill(-1.0);
	develop.slice(develop.n_slices-1).fill(arma::fill::zeros);

//	LOG(INFO) << "Calculate resist profile development";
	eikonal::solve3d(develop, rates, result->stepy(), result->stepx(), result->stepz());
#else
	*result->values() = rates;
#endif

	return result;
}


SharedResistProfile resist_profile(SharedResistVolume develop_times, SharedDevelopment development) {
	return std::make_shared<ResistProfile>(develop_times, development->time);
}
