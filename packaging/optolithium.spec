Name:           optolithium
Version:        %{?pkg_version}%{!?pkg_version:0.5.0}
Release:        %{?pkg_release}%{!?pkg_release:1}%{?dist}
Summary:        Modern Optical Lithography Simulation Suite
License:        GPL-2.0-or-later
URL:            https://bitbucket.org/gladkikhalexei/lithography
Group:          Applications/Engineering
BuildArch:      x86_64

# Turn off automatic dependency scanning for bundled private libraries
AutoReqProv:    no

# Prevent RPM post-processing from failing on bundled wheels and libraries
%global debug_package %{nil}
%global __brp_check_rpaths %{nil}
%global __brp_mangle_shebangs %{nil}
%global __brp_python_bytecompile %{nil}
%global __brp_python_rpm_in_distinfo %{nil}
%global __brp_strip %{nil}
%global __brp_strip_lto %{nil}
%global __brp_strip_comment_note %{nil}
%global __brp_strip_static_archive %{nil}
%define _build_id_links none
%define __check_files %{nil}
%define _unpackaged_files_terminate_build 0

Requires:       /bin/sh
Requires:       /usr/bin/env

%description
Optolithium is an optical lithography simulation and modeling software suite.
It provides advanced physical optical simulations, partial coherent imaging,
resist exposure, post-exposure bake (PEB), development rate models, and
rigorous metrology analysis.
This package is fully self-contained with zero runtime dependencies.

%install
mkdir -p %{buildroot}
cp -a %{staged_root}/* %{buildroot}/

%post
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi

%postun
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi

%files
/usr/bin/optolithium
/usr/share/applications/optolithium.desktop
/usr/share/icons/hicolor/128x128/apps/optolithium.png
/usr/share/pixmaps/optolithium.png
/usr/share/man/man1/optolithium.1*
/opt/optolithium

%changelog
* Tue Oct 20 2026 Rudra <rudra@local> - 0.3.0-1
- Fully self-contained zero-dependency release
