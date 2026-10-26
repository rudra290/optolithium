# This file is part of Optolithium lithography modelling software.
#
# Copyright (C) 2015 Alexei Gladkikh
#
# This software is dual-licensed: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version only for NON-COMMERCIAL usage.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# If you are interested in other licensing models, including a commercial-
# license, please contact the author at gladkikhalexei@gmail.com

import math
import os
import psutil
import optolithiumc as oplc
import logging as module_logging
import helpers

from numpy import angle
from qt import QtCore, Signal, connect, QSlot
from metrics import IMAGE_NEGATIVE, IMAGE_POSITIVE, \
    CONTOUR_METRICS, IMAGE_METRICS, PROFILE_METRICS, STANDING_WAVES_METRICS
from simulation_memory import estimate_aerial_worker_memory_bytes, estimate_resist_grid, \
    estimate_volume_resident_bytes, estimate_develop_contours_resident_bytes


__author__ = 'Alexei Gladkikh'


logging = module_logging.getLogger(__name__)
logging.setLevel(module_logging.INFO)
helpers.logStreamEnable(logging)


def _available_memory_bytes():
    available = psutil.virtual_memory().available
    # psutil reports host memory in some containers; account for the container
    # limit as well so Linux does not kill the process during a large allocation.
    for limit_path, usage_path in (
            ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory.current"),
            ("/sys/fs/cgroup/memory/memory.limit_in_bytes",
             "/sys/fs/cgroup/memory/memory.usage_in_bytes")):
        try:
            with open(limit_path, "r") as limit_file:
                limit_text = limit_file.read().strip()
            if limit_text == "max":
                continue
            limit = int(limit_text)
            # cgroup v1 uses a very large number to mean "unlimited".
            if limit > psutil.virtual_memory().total * 2:
                continue
            with open(usage_path, "r") as usage_file:
                usage = int(usage_file.read().strip())
            reclaimable_file_cache = 0
            stat_path = os.path.join(os.path.dirname(usage_path), "memory.stat")
            memory_stats = {}
            try:
                with open(stat_path, "r") as stat_file:
                    for line in stat_file:
                        values = line.split(None, 1)
                        if len(values) == 2:
                            memory_stats[values[0]] = values[1].strip()
            except (IOError, OSError):
                pass
            if limit_path.endswith("memory.max"):
                file_cache = int(memory_stats.get("file", 0))
                shared_memory = int(memory_stats.get("shmem", 0))
                reclaimable_file_cache = max(0, file_cache - shared_memory)
            else:
                reclaimable_file_cache = int(memory_stats.get(
                    "inactive_file", memory_stats.get("total_inactive_file", 0)))
            effective_usage = max(0, usage - reclaimable_file_cache)
            available = min(available, max(0, limit - effective_usage))
        except (IOError, OSError, ValueError):
            continue
    return available


def _require_simulation_memory(stage_name, requested_bytes):
    """Fail before a large allocation if the available memory is too low."""
    available_bytes = _available_memory_bytes()
    # Reserve 30% of currently available memory for allocator overhead,
    # FFT plans, and other process activity.
    if requested_bytes > available_bytes * 0.70:
        raise MemoryError(
            "%s is estimated to need about %.1f GiB, but only %.1f GiB is "
            "available with the 30%% safety reserve. Increase the X/Y or Z grid spacing "
            "in Numerics and try again." % (
                stage_name,
                requested_bytes / float(1024 ** 3),
                available_bytes / float(1024 ** 3)))


def _diffraction_axis_count(numerical_aperture, wavelength, pitch, source_min, source_max):
    if pitch == 0.0 or wavelength <= 0.0:
        return 1
    k_min = -int(math.floor(numerical_aperture * (1.0 - source_min) / wavelength * pitch))
    k_max = int(math.floor(numerical_aperture * (1.0 + source_max) / wavelength * pitch))
    return max(1, k_max - k_min + 1)


def _resist_volume_bytes(volume):
    # ArmaNpy exposes the native cube through a shared-memory NumPy view.
    return int(volume.values.nbytes)

core_logging = oplc.OptolithiumCoreLog()
core_logging.set_verbose_level(4)

LOG_VERBOSE_0 = 0

# set_printoptions(linewidth=nan, precision=3, threshold=nan)


class CoreSimulationOptions(object):

    def __init__(self, options):
        """:type options: options.structures.Options"""
        self.__options = options

        self.__mask = None
        self.__imaging_tool = None
        self.__wafer_stack = None
        self.__exposure = None
        self.__peb = None
        self.__development = None

    @property
    def options(self):
        return self.__options

    def numerics(self, changed=None):
        if changed is not None:
            changed.append(not self.__options.numerics.is_simulated)
        self.__options.numerics.simulated()
        return self.__options.numerics

    def mask(self, changed=None):
        if not self.__options.mask.is_simulated or self.__mask is None:
            if changed is not None:
                changed.append(True)
            self.__mask = self.__options.mask.convert2core()
            self.__options.mask.simulated()
        elif changed is not None:
            changed.append(False)
        return self.__mask

    def imaging_tool(self, changed=None):
        if not self.__options.imaging_tool.is_simulated or self.__imaging_tool is None:
            if changed is not None:
                changed.append(True)
            self.__imaging_tool = self.__options.imaging_tool.convert2core()
            self.__options.imaging_tool.simulated()
        elif changed is not None:
            changed.append(False)
        return self.__imaging_tool

    def wafer_stack(self, changed=None):
        if not self.__options.wafer_process.is_simulated or self.__wafer_stack is None:
            if changed is not None:
                changed.append(True)
            self.__wafer_stack = self.__options.wafer_process.convert2core()
            self.__options.wafer_process.simulated()
        elif changed is not None:
            changed.append(False)
        return self.__wafer_stack

    def exposure(self, changed=None):
        if not self.__options.exposure_focus.is_simulated or self.__exposure is None:
            if changed is not None:
                changed.append(True)
            self.__exposure = self.__options.exposure_focus.convert2core()
            self.__options.exposure_focus.simulated()
        elif changed is not None:
            changed.append(False)
        return self.__exposure

    def post_exposure_bake(self, changed=None):
        if not self.__options.peb.is_simulated or self.__peb is None:
            if changed is not None:
                changed.append(True)
            self.__peb = self.__options.peb.convert2core()
            self.__options.peb.simulated()
        elif changed is not None:
            changed.append(False)
        return self.__peb

    def development(self, changed=None):
        if not self.__options.development.is_simulated or self.__development is None:
            if changed is not None:
                changed.append(True)
            self.__development = self.__options.development.convert2core()
            self.__options.development.simulated()
        elif changed is not None:
            changed.append(False)
        return self.__development


class AbstractStage(QtCore.QObject):

    invalidated = Signal()

    def __init__(self, core_options, metrics, pre_stage=None):
        """
        :type core_options: CoreSimulationOptions
        :type pre_stage: AbstractStage or None
        """
        super(AbstractStage, self).__init__()

        self.__core_options = core_options

        self.__pre_stage = pre_stage
        """:type: AbstractStage or None"""

        if self.__pre_stage is not None:
            self.__pre_stage.add_post_stage(self)

        self.__post_stages = []
        """:type: list of AbstractStage"""

        self.__result = None

        self.__metrics = [metric_class(self) for metric_class in metrics]

    @property
    def name(self):
        """:rtype: str"""
        raise NotImplementedError

    @property
    def pre_stage(self):
        return self.__pre_stage

    def add_post_stage(self, stage):
        """:type: AbstractStage"""
        self.__post_stages.append(stage)

    @property
    def has_result(self):
        return self.__result is not None

    @QSlot()
    def invalidate(self):
        # logging.info("Invalidate: %s" % self.__class__.__name__)
        self.__result = None
        for stage in self.__post_stages:
            # if stage.has_result:
            stage.invalidate()
        self.invalidated.emit()

    @property
    def core_options(self):
        return self.__core_options

    @property
    def options(self):
        return self.core_options.options

    def _payload(self):
        """:rtype: optolithiumc.Diffraction or optolithiumc.ResistVolume"""
        raise NotImplementedError

    @property
    def metrics_kwargs(self):
        """:rtype: dict from str"""
        return dict()

    @property
    def metrics(self):
        """:rtype: list of metrology.MetrologyInterface"""
        return self.__metrics

    def calculate(self):
        logging.debug("Calculate %s" % self.__class__.__name__)
        if not self.has_result:
            self.__result = self._payload()
        else:
            logging.debug("%s not changed" % self.__class__.__name__)
        return self.__result


class DiffractionStage(AbstractStage):

    def __init__(self, core_options):
        super(DiffractionStage, self).__init__(core_options, [])

    @property
    def name(self):
        return "Diffraction"

    def _payload(self, *args):
        mask = self.core_options.mask()
        imaging_tool = self.core_options.imaging_tool()

        pitch = mask.pitch()
        source_shape = imaging_tool.source_shape()
        cols = _diffraction_axis_count(
            imaging_tool.numeric_aperture, imaging_tool.wavelength, pitch.x,
            source_shape.sx_min(), source_shape.sx_max())
        rows = _diffraction_axis_count(
            imaging_tool.numeric_aperture, imaging_tool.wavelength, pitch.y,
            source_shape.sy_min(), source_shape.sy_max())
        diffraction_bytes = rows * cols * 24 + (rows + cols) * 64
        _require_simulation_memory("Diffraction", diffraction_bytes)

        diffraction = oplc.diffraction(imaging_tool, mask)

        logging.log(
            LOG_VERBOSE_0,
            "Calculated diffraction pattern with value shape [%s].",
            diffraction.values.shape)

        return diffraction


class AerialImageStage(AbstractStage):

    def __init__(self, core_options, pre_stage):
        super(AerialImageStage, self).__init__(core_options, metrics=IMAGE_METRICS, pre_stage=pre_stage)

    @property
    def name(self):
        return "Aerial Image"

    def _payload(self):
        diffraction = self.pre_stage.calculate()

        numerics = self.core_options.numerics()
        imaging_tool = self.core_options.imaging_tool()
        exposure_focus = self.core_options.exposure()

        pitch = diffraction.pitch
        nx, ny, _ = estimate_resist_grid(
            pitch.x, pitch.y, 0.0, numerics.grid_xy.value, numerics.grid_z.value)
        plane_bytes = nx * ny * 8
        worker_bytes = estimate_aerial_worker_memory_bytes(nx, ny)
        _require_simulation_memory("Aerial Image", plane_bytes + worker_bytes)

        otf = oplc.OpticalTransferFunction(imaging_tool, exposure_focus)
        aerial_image = oplc.aerial_image(diffraction, otf, numerics.grid_xy.value)

        logging.log(
            LOG_VERBOSE_0,
            "Calculated aerial image with value shape [%s].",
            aerial_image.values.shape)

        return aerial_image

    @property
    def metrics_kwargs(self):
        return {
            "level": self.options.metrology.aerial_image_level.value
        }


def _magnitude(v):
    return (v * v.conjugate()).real


def _phase(v):
    return angle(v, deg=True)


class StandingWavesStage(AbstractStage):

    def __init__(self, core_options):
        super(StandingWavesStage, self).__init__(core_options, metrics=STANDING_WAVES_METRICS)

    @property
    def name(self):
        return "Standing Waves"

    def _payload(self):
        wafer_stack = self.core_options.wafer_stack()
        wavelength = self.core_options.imaging_tool().wavelength
        resist_indx = wafer_stack.index_of(wafer_stack.resist())
        resist_reflectivity = wafer_stack.reflectivity(resist_indx, wavelength)
        substrate_reflectivity = wafer_stack.reflectivity(resist_indx+1, wavelength)
        return {
            "resist_reflectivity": _magnitude(resist_reflectivity),
            "resist_phase": _phase(resist_reflectivity),
            "substrate_reflectivity": _magnitude(substrate_reflectivity),
            "substrate_phase": _phase(substrate_reflectivity)
        }


class ImageInResistStage(AbstractStage):

    def __init__(self, core_options, pre_stage):
        super(ImageInResistStage, self).__init__(core_options, metrics=IMAGE_METRICS, pre_stage=pre_stage)

    @property
    def name(self):
        return "Image in Resist"

    def _payload(self):
        diffraction = self.pre_stage.calculate()

        numerics = self.core_options.numerics()
        wafer_stack = self.core_options.wafer_stack()
        imaging_tool = self.core_options.imaging_tool()
        exposure = self.core_options.exposure()

        otf = oplc.OpticalTransferFunction(imaging_tool, exposure, wafer_stack)

        # Refuse allocations that are likely to trigger the OS OOM killer. A
        # resist volume is much larger than its 2D image because every Z slice
        # stores a full XY plane.
        pitch = diffraction.pitch
        grid_xy = numerics.grid_xy.value
        grid_z = numerics.grid_z.value
        nx, ny, nz = estimate_resist_grid(
            pitch.x, pitch.y, wafer_stack.resist().thickness, grid_xy, grid_z)
        volume_bytes = nx * ny * nz * 8
        worker_bytes = estimate_aerial_worker_memory_bytes(
            nx, ny, with_reflection_cache=True)
        plane_bytes = nx * ny * 8
        _require_simulation_memory(
            "Image in Resist", worker_bytes + estimate_volume_resident_bytes(plane_bytes))

        image_in_resist = oplc.image_in_resist(diffraction, otf, numerics.grid_xy.value, numerics.grid_z.value)

        logging.log(
            LOG_VERBOSE_0,
            "Calculated image in resist with value shape [%s].",
            image_in_resist.values.shape)
        return image_in_resist

    @property
    def metrics_kwargs(self):
        return {
            "title": "Relative Intensity",
            "level": self.options.metrology.image_in_resist_level.value,
            "image_tonality": IMAGE_NEGATIVE,
            "tonality": self.options.metrology.mask_tonality.value,
            "height": self.options.metrology.measurement_height.value,
        }


class LatentImageStage(AbstractStage):

    def __init__(self, core_options, pre_stage):
        super(LatentImageStage, self).__init__(core_options, metrics=IMAGE_METRICS, pre_stage=pre_stage)

    @property
    def name(self):
        return "Exposed Latent Image in Resist"

    def _payload(self):
        image_in_resist = self.pre_stage.calculate()

        resist = oplc.ResistWaferLayer.cast(self.core_options.wafer_stack().resist())
        exposure = self.core_options.exposure()

        _require_simulation_memory(
            "Exposed Latent Image",
            estimate_volume_resident_bytes(_resist_volume_bytes(image_in_resist)))

        latent_image = oplc.latent_image(image_in_resist, resist, exposure)

        logging.log(
            LOG_VERBOSE_0,
            "Calculated exposed latent image with value shape [%s].",
            latent_image.values.shape)
        return latent_image

    @property
    def metrics_kwargs(self):
        return {
            "title": "Relative PAC Concentration",
            "level": self.options.metrology.latent_image_level.value,
            "image_tonality": IMAGE_POSITIVE,
            "tonality": self.options.metrology.mask_tonality.value,
            "height": self.options.metrology.measurement_height.value,
        }


class PebLatentImageStage(AbstractStage):

    def __init__(self, core_options, pre_stage):
        super(PebLatentImageStage, self).__init__(core_options, metrics=IMAGE_METRICS, pre_stage=pre_stage)

    @property
    def name(self):
        return "Latent Image in Resist after PEB"

    def _payload(self):
        latent_image = self.pre_stage.calculate()

        resist = oplc.ResistWaferLayer.cast(self.core_options.wafer_stack().resist())
        peb = self.core_options.post_exposure_bake()

        _require_simulation_memory(
            "PEB Latent Image", estimate_volume_resident_bytes(_resist_volume_bytes(latent_image)))

        peb_latent_image = oplc.peb_latent_image(latent_image, resist, peb)

        logging.log(
            LOG_VERBOSE_0,
            "Calculated PEB latent image with value shape [%s].",
            peb_latent_image.values.shape)
        return peb_latent_image

    @property
    def metrics_kwargs(self):
        return {
            "title": "Relative PAC Concentration",
            "level": self.options.metrology.peb_latent_image_level.value,
            "image_tonality": IMAGE_POSITIVE,
            "tonality": self.options.metrology.mask_tonality.value,
            "height": self.options.metrology.measurement_height.value,
        }


class DevelopContoursStage(AbstractStage):

    def __init__(self, core_options, pre_stage):
        super(DevelopContoursStage, self).__init__(core_options, metrics=CONTOUR_METRICS, pre_stage=pre_stage)

    @property
    def name(self):
        return "Develop Time Contours"

    def _payload(self):
        peb_latent_image = self.pre_stage.calculate()

        resist = oplc.ResistWaferLayer.cast(self.core_options.wafer_stack().resist())

        # The result and rate cubes are disk-backed, but the fast-marching
        # solver uses per-voxel status arrays and a growing in-memory heap.
        volume_bytes = _resist_volume_bytes(peb_latent_image)
        voxel_count = volume_bytes // 8
        if voxel_count > 0x7fffffff:
            raise MemoryError(
                "Develop Time Contours has %d voxels, beyond the solver's "
                "32-bit grid-index limit. Increase the X/Y or Z grid spacing "
                "in Numerics and try again." % voxel_count)
        _require_simulation_memory(
            "Develop Time Contours",
            estimate_develop_contours_resident_bytes(volume_bytes))

        develop_contours = oplc.develop_time_contours(peb_latent_image, resist)

        logging.log(
            LOG_VERBOSE_0,
            "Calculated develop time contours with value shape [%s].",
            develop_contours.values.shape)
        return develop_contours

    @property
    def metrics_kwargs(self):
        return {
            "level": self.options.development.develop_time.value,
            "image_tonality": IMAGE_POSITIVE,
            "tonality": self.options.metrology.mask_tonality.value,
            "height": self.options.metrology.measurement_height.value,
            "variate_height": self.options.metrology.variate_meas_height.value,
        }


class ResistProfileStage(AbstractStage):

    def __init__(self, core_options, pre_stage):
        super(ResistProfileStage, self).__init__(core_options, metrics=PROFILE_METRICS, pre_stage=pre_stage)

    @property
    def name(self):
        return "Resist Profile"

    def _payload(self):
        if not self.core_options.mask().is_1d():
            raise ValueError(
                "Resist Profile simulation is not supported for 3D mask features. "
                "Only 1D line/space masks are supported for profile extraction.")
        develop_contours = self.pre_stage.calculate()
        develop_time = self.core_options.development()
        resist_profile = oplc.resist_profile(develop_contours, develop_time)
        return resist_profile

    @property
    def metrics_kwargs(self):
        return {
            "tonality": self.options.metrology.mask_tonality.value,
            "height": self.options.metrology.measurement_height.value,
            "variate_height": self.options.metrology.variate_meas_height.value,
        }


class Core(QtCore.QObject):

    def __init__(self, options, *args, **kwargs):
        """:type options: options.structures.Options"""
        super(Core, self).__init__(*args, **kwargs)
        self.__options = options
        core_options = CoreSimulationOptions(options)
        self.__standing_waves_stage = StandingWavesStage(core_options)
        self.__diffraction_stage = DiffractionStage(core_options)
        self.__aerial_image_stage = AerialImageStage(core_options, self.__diffraction_stage)
        self.__image_in_resist_stage = ImageInResistStage(core_options, self.__diffraction_stage)
        self.__latent_image_stage = LatentImageStage(core_options, self.__image_in_resist_stage)
        self.__peb_latent_image_stage = PebLatentImageStage(core_options, self.__latent_image_stage)
        self.__develop_contours_stage = DevelopContoursStage(core_options, self.__peb_latent_image_stage)
        self.__resist_profile_stage = ResistProfileStage(core_options, self.__develop_contours_stage)

        self.__stages = [
            self.standing_waves, self.diffraction,
            self.aerial_image, self.image_in_resist,
            self.latent_image, self.peb_latent_image,
            self.develop_contours, self.resist_profile
        ]

        logging.info("Connect numerics signals to core")
        connect(
            self.__options.numerics.changed,
            self.__standing_waves_stage.invalidate,
            self.__aerial_image_stage.invalidate,
            self.__image_in_resist_stage.invalidate
        )

        logging.info("Connect wafer process signals to core")
        connect(
            self.__options.wafer_process.changed,
            self.__standing_waves_stage.invalidate,
            self.__image_in_resist_stage.invalidate,
        )

        logging.info("Connect resist signals to core")
        connect(
            self.__options.wafer_process.resist.changed,
            self.__standing_waves_stage.invalidate,
            self.__develop_contours_stage.invalidate,
        )

        logging.info("Connect mask signals to core")
        connect(
            self.__options.mask.changed,
            self.__diffraction_stage.invalidate
        )

        logging.info("Connect imaging tool signals to core")
        connect(
            self.__options.imaging_tool.changed,
            self.__standing_waves_stage.invalidate,
            self.__diffraction_stage.invalidate,
        )

        logging.info("Connect exposure focus signals to core")
        connect(
            self.__options.exposure_focus.changed,
            self.__aerial_image_stage.invalidate,
            self.__image_in_resist_stage.invalidate
        )

        logging.info("Connect peb signals to core")
        connect(
            self.__options.peb.changed,
            self.__peb_latent_image_stage.invalidate
        )

        logging.info("Connect development signals to core")
        connect(
            self.__options.development.changed,
            self.__resist_profile_stage.invalidate
        )

    @property
    def options(self):
        return self.__options

    def __iter__(self):
        return self.__stages.__iter__()

    standing_waves = property(lambda self: self.__standing_waves_stage)
    diffraction = property(lambda self: self.__diffraction_stage)
    aerial_image = property(lambda self: self.__aerial_image_stage)
    image_in_resist = property(lambda self: self.__image_in_resist_stage)
    latent_image = property(lambda self: self.__latent_image_stage)
    peb_latent_image = property(lambda self: self.__peb_latent_image_stage)
    develop_contours = property(lambda self: self.__develop_contours_stage)
    resist_profile = property(lambda self: self.__resist_profile_stage)
