#!/usr/bin/env python3
# ==============================================================================
# Script to generate WiX (.wxs) XML file for Optolithium Windows MSI Installer
# ==============================================================================
import os
import sys
import uuid
import re
import argparse
import xml.etree.ElementTree as ET
from xml.dom import minidom

UPGRADE_CODE = "{4B614687-8FB0-4599-9BD8-2CC3EC563821}"
NS_UUID = uuid.UUID("4B614687-8FB0-4599-9BD8-2CC3EC563821")


def sanitize_id(prefix, path):
    clean = re.sub(r'[^a-zA-Z0-9_]', '_', path)
    if len(clean) > 55:
        import hashlib
        h = hashlib.md5(path.encode()).hexdigest()[:8]
        clean = clean[:45] + '_' + h
    return f"{prefix}_{clean}".strip('_')


def build_wxs(staging_dir, version, output_wxs):
    app_dir = os.path.join(staging_dir, "app")

    # Collect files
    dir_tree = {}
    component_refs = []

    # Map directories and components
    wix_dir_xml = []

    def walk_dir(current_dir, parent_xml_indent=8):
        nonlocal wix_dir_xml
        entries = sorted(os.listdir(current_dir))
        files = []
        subdirs = []
        for e in entries:
            full = os.path.join(current_dir, e)
            if os.path.isdir(full):
                subdirs.append(e)
            elif os.path.isfile(full):
                files.append(e)

        indent = " " * parent_xml_indent
        lines = []

        if files:
            rel_dir = os.path.relpath(current_dir, staging_dir).replace("\\", "/")
            cmp_id = sanitize_id("cmp", rel_dir)
            cmp_guid = str(uuid.uuid5(NS_UUID, "comp/" + rel_dir)).upper()
            component_refs.append(cmp_id)

            lines.append(f'{indent}<Component Id="{cmp_id}" Guid="{{{cmp_guid}}}">')
            for f in files:
                rel_file = os.path.relpath(os.path.join(current_dir, f), staging_dir).replace("\\", "/")
                file_id = sanitize_id("fil", rel_file)
                source_path = rel_file.replace("\\", "/")
                lines.append(f'{indent}  <File Id="{file_id}" Source="{source_path}" KeyPath="{"yes" if f == files[0] else "no"}" />')
            lines.append(f'{indent}</Component>')

        for d in subdirs:
            rel_subdir = os.path.relpath(os.path.join(current_dir, d), staging_dir).replace("\\", "/")
            dir_id = sanitize_id("dir", rel_subdir)
            lines.append(f'{indent}<Directory Id="{dir_id}" Name="{d}">')
            lines.extend(walk_dir(os.path.join(current_dir, d), parent_xml_indent + 2))
            lines.append(f'{indent}</Directory>')

        return lines

    app_structure_lines = walk_dir(app_dir, 12)

    component_refs_xml = "\n".join([f'      <ComponentRef Id="{c}" />' for c in component_refs])

    wxs_template = f"""<?xml version="1.0" encoding="utf-8"?>
<Wix xmlns="http://schemas.microsoft.com/wix/2006/wi">
  <Product Id="*"
           Name="Optolithium"
           Language="1033"
           Version="{version}"
           Manufacturer="Optolithium Team"
           UpgradeCode="{UPGRADE_CODE}">
    <Package InstallerVersion="200"
             Compressed="yes"
             InstallScope="perMachine"
             Description="Optolithium Optical Lithography Simulation Suite"
             Comments="Modelling software for optical lithography simulation" />

    <MajorUpgrade DowngradeErrorMessage="A newer version of Optolithium is already installed." />
    <MediaTemplate EmbedCab="yes" />

    <Icon Id="AppIcon" SourceFile="icon.ico" />
    <Property Id="ARPPRODUCTICON" Value="AppIcon" />
    <Property Id="ARPHELPLINK" Value="https://bitbucket.org/gladkikhalexei/lithography" />
    <Property Id="ARPURLINFOABOUT" Value="https://bitbucket.org/gladkikhalexei/lithography" />

    <Directory Id="TARGETDIR" Name="SourceDir">
      <Directory Id="ProgramFiles64Folder">
        <Directory Id="INSTALLFOLDER" Name="Optolithium">
          <Component Id="cmp_launcher" Guid="{{{str(uuid.uuid5(NS_UUID, "launcher")).upper()}}}">
            <File Id="fil_launcher_bat" Source="optolithium.bat" KeyPath="yes" />
            <File Id="fil_launcher_cli" Source="optolithium-cli.bat" />
            <File Id="fil_icon_ico" Source="icon.ico" />
          </Component>
          <Directory Id="dir_app" Name="app">
{chr(10).join(app_structure_lines)}
          </Directory>
        </Directory>
      </Directory>

      <Directory Id="ProgramMenuFolder">
        <Directory Id="ApplicationProgramsFolder" Name="Optolithium" />
      </Directory>

      <Directory Id="DesktopFolder" Name="Desktop" />
    </Directory>

    <DirectoryRef Id="ApplicationProgramsFolder">
      <Component Id="cmp_shortcuts" Guid="{{{str(uuid.uuid5(NS_UUID, "shortcuts")).upper()}}}">
        <Shortcut Id="ApplicationStartMenuShortcut"
                  Name="Optolithium"
                  Description="Optical Lithography Simulation Software"
                  Target="[INSTALLFOLDER]optolithium.bat"
                  WorkingDirectory="INSTALLFOLDER"
                  Icon="AppIcon" />
        <Shortcut Id="UninstallProductShortcut"
                  Name="Uninstall Optolithium"
                  Description="Uninstalls Optolithium"
                  Target="[SystemFolder]msiexec.exe"
                  Arguments="/x [ProductCode]" />
        <RemoveFolder Id="CleanUpShortCut" On="uninstall" />
        <RegistryValue Root="HKCU" Key="Software\\Optolithium" Name="installed" Type="integer" Value="1" KeyPath="yes" />
      </Component>
    </DirectoryRef>

    <DirectoryRef Id="DesktopFolder">
      <Component Id="cmp_desktop_shortcut" Guid="{{{str(uuid.uuid5(NS_UUID, "desktop")).upper()}}}">
        <Shortcut Id="ApplicationDesktopShortcut"
                  Name="Optolithium"
                  Description="Optical Lithography Simulation Software"
                  Target="[INSTALLFOLDER]optolithium.bat"
                  WorkingDirectory="INSTALLFOLDER"
                  Icon="AppIcon" />
        <RegistryValue Root="HKCU" Key="Software\\Optolithium" Name="desktop_shortcut" Type="integer" Value="1" KeyPath="yes" />
      </Component>
    </DirectoryRef>

    <Feature Id="ProductFeature" Title="Optolithium" Level="1">
      <ComponentRef Id="cmp_launcher" />
      <ComponentRef Id="cmp_shortcuts" />
      <ComponentRef Id="cmp_desktop_shortcut" />
{component_refs_xml}
    </Feature>
  </Product>
</Wix>
"""

    with open(output_wxs, "w", encoding="utf-8") as f:
        f.write(wxs_template)

    print(f"Generated WiX specification: {output_wxs} ({len(component_refs) + 3} components)")


def main():
    parser = argparse.ArgumentParser(description="Generate WiX .wxs for Optolithium")
    parser.add_argument("--staging-dir", required=True, help="Directory containing staged files")
    parser.add_argument("--version", default="0.3.0", help="Application version")
    parser.add_argument("--output", required=True, help="Output .wxs file path")
    args = parser.parse_args()

    build_wxs(args.staging_dir, args.version, args.output)


if __name__ == "__main__":
    main()
