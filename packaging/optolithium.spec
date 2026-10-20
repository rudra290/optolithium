Name:           optolithium
Version:        %{?pkg_version}%{!?pkg_version:0.3.0}
Release:        %{?pkg_release}%{!?pkg_release:1}%{?dist}
Summary:        Modern Optical Lithography Simulation Suite
License:        GPL-2.0-or-later
URL:            https://bitbucket.org/gladkikhalexei/lithography
Group:          Applications/Engineering
BuildArch:      x86_64

# Prevent RPM post-processing from corrupting Python virtualenv or shared libraries
%global debug_package %{nil}
%global __brp_python_bytecompile %{nil}
%global __brp_mangle_shebangs %{nil}
%global __strip /bin/true
%define _build_id_links none

Requires:       python3 >= 3.10
Requires:       fftw-libs
Requires:       libstdc++

%description
Optolithium is an optical lithography simulation and modeling software suite.
It provides advanced physical optical simulations, partial coherent imaging,
resist exposure, post-exposure bake (PEB), development rate models, and
rigorous metrology analysis.

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
/opt/optolithium

%changelog
* Tue Oct 20 2026 Rudra <rudra@local> - 0.3.0-1
- Modernized Linux release with RPM and DNF package management support

