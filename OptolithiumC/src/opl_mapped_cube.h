#ifndef OPTOLITHIUM_MAPPED_CUBE_H
#define OPTOLITHIUM_MAPPED_CUBE_H

#include <armadillo>

#include <cerrno>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#if !defined(_WIN32)
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#if defined(__linux__)
#include <sys/vfs.h>
#endif
#endif

namespace oplc {
namespace storage {

static const size_t MAPPED_CUBE_THRESHOLD_BYTES = 64u * 1024u * 1024u;

#if !defined(_WIN32)

inline std::string simulation_storage_directory(void) {
	const char* configured = std::getenv("OPTOLITHIUM_SIMULATION_STORAGE");
	if (configured && configured[0] != '\0') {
		return configured;
	}
	const char* xdg_cache = std::getenv("XDG_CACHE_HOME");
	if (xdg_cache && xdg_cache[0] == '/') {
		return std::string(xdg_cache) + "/optolithium/simulation";
	}
	const char* home = std::getenv("HOME");
	if (!home || home[0] == '\0') {
		throw std::runtime_error(
			"Disk-backed simulation volumes need HOME or OPTOLITHIUM_SIMULATION_STORAGE.");
	}
	return std::string(home) + "/.cache/optolithium/simulation";
}

inline void ensure_storage_directory(const std::string& path) {
	if (path.empty()) {
		throw std::runtime_error("The simulation storage directory is empty.");
	}
	for (size_t end = 1; end <= path.size(); ++end) {
		if (end != path.size() && path[end] != '/') {
			continue;
		}
		std::string component = path.substr(0, end);
		if (component.empty()) {
			continue;
		}
		if (mkdir(component.c_str(), 0700) != 0 && errno != EEXIST) {
			throw std::runtime_error("Cannot create simulation storage directory '" +
				component + "': " + std::strerror(errno));
		}
		struct stat info;
		if (stat(component.c_str(), &info) != 0 || !S_ISDIR(info.st_mode)) {
			throw std::runtime_error("Simulation storage path component is not a directory: '" +
				component + "'.");
		}
	}
}

class MappedFile {
private:
	int _fd;
	void* _address;
	size_t _size;
	std::string _path;

	void cleanup(void) {
		if (_address != MAP_FAILED) {
			munmap(_address, _size);
			_address = MAP_FAILED;
		}
		if (_fd >= 0) {
			close(_fd);
			_fd = -1;
		}
		if (!_path.empty()) {
			unlink(_path.c_str());
			_path.clear();
		}
	}

public:
	explicit MappedFile(size_t bytes) : _fd(-1), _address(MAP_FAILED), _size(bytes) {
		if (bytes == 0 || bytes > static_cast<size_t>(std::numeric_limits<off_t>::max())) {
			throw std::length_error("Invalid disk-backed simulation volume size.");
		}
		const std::string directory = simulation_storage_directory();
		ensure_storage_directory(directory);
#if defined(__linux__)
		struct statfs filesystem;
		if (statfs(directory.c_str(), &filesystem) == 0 &&
				(static_cast<unsigned long>(filesystem.f_type) == 0x01021994ul ||
				 static_cast<unsigned long>(filesystem.f_type) == 0x858458f6ul)) {
			throw std::runtime_error(
				"Simulation storage is on a RAM-backed filesystem. Set "
				"OPTOLITHIUM_SIMULATION_STORAGE to a disk-backed directory.");
		}
#endif
		_path = directory + "/optolithium-volume-XXXXXX";
		std::vector<char> template_path(_path.begin(), _path.end());
		template_path.push_back('\0');
		_fd = mkstemp(template_path.data());
		if (_fd < 0) {
			_path.clear();
			throw std::runtime_error("Cannot create disk-backed simulation volume in '" +
				directory + "': " + std::strerror(errno));
		}
		_path.assign(template_path.data());
		try {
			if (ftruncate(_fd, static_cast<off_t>(bytes)) != 0) {
				throw std::runtime_error("Cannot size disk-backed simulation volume: " +
					std::string(std::strerror(errno)));
			}
			int allocation_error = posix_fallocate(_fd, 0, static_cast<off_t>(bytes));
			if (allocation_error != 0) {
				throw std::runtime_error("Cannot reserve " + std::to_string(bytes) +
					" bytes for a simulation volume: " + std::strerror(allocation_error));
			}
			_address = mmap(NULL, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, _fd, 0);
			if (_address == MAP_FAILED) {
				throw std::runtime_error("Cannot map disk-backed simulation volume: " +
					std::string(std::strerror(errno)));
			}
			if (unlink(_path.c_str()) == 0) {
				_path.clear();
			}
		} catch (...) {
			cleanup();
			throw;
		}
	}

	~MappedFile(void) {
		cleanup();
	}

	void* data(void) const {
		return _address;
	}
};

#endif

inline std::shared_ptr<arma::cube> make_cube(arma::uword rows, arma::uword cols,
		arma::uword slices) {
	if (rows != 0 && cols > std::numeric_limits<size_t>::max() / rows) {
		throw std::length_error("Simulation volume dimensions are too large.");
	}
	const size_t plane = static_cast<size_t>(rows) * cols;
	if (plane != 0 && slices > std::numeric_limits<size_t>::max() / plane) {
		throw std::length_error("Simulation volume dimensions are too large.");
	}
	const size_t bytes = plane * static_cast<size_t>(slices) * sizeof(double);
#if !defined(_WIN32)
	if (slices > 1 && bytes >= MAPPED_CUBE_THRESHOLD_BYTES) {
		std::shared_ptr<MappedFile> backing = std::make_shared<MappedFile>(bytes);
		arma::cube* cube = new arma::cube(static_cast<double*>(backing->data()),
			rows, cols, slices, false, true);
		return std::shared_ptr<arma::cube>(cube, [backing](arma::cube* value) {
			delete value;
		});
	}
#endif
	return std::make_shared<arma::cube>(rows, cols, slices);
}

} // namespace storage
} // namespace oplc

#endif
