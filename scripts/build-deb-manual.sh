#!/bin/bash
# Manual Debian Package Builder for Arch Linux
# This script assembles the package structure manually and uses dpkg-deb to build it.

set -e

VERSION="1.8"
RELEASE="1"
PKGNAME="baleno"
ARCH="all"
BUILD_DIR="build-deb/${PKGNAME}_${VERSION}-${RELEASE}_${ARCH}"

echo "=== Baleno Manual Debian Package Builder ==="
echo "Version: ${VERSION}"
echo "Build Directory: ${BUILD_DIR}"
echo ""

# Check if running from project root
if [ ! -f "baleno" ] || [ ! -d "assets" ]; then
    echo "Error: Please run this script from the project root directory."
    exit 1
fi

# Check for dpkg-deb
if ! command -v dpkg-deb &> /dev/null; then
    echo "Error: dpkg-deb not found."
    echo "Please install dpkg: sudo pacman -S dpkg"
    exit 1
fi

# Bundle the modular source into a single executable
echo "Bundling balenolib into dist/baleno..."
python3 scripts/bundle-monolith.py

# Clean previous build
echo "Cleaning build directory..."
rm -rf build-deb

# Create directory structure
echo "Creating directory structure..."
mkdir -p "${BUILD_DIR}/DEBIAN"
mkdir -p "${BUILD_DIR}/usr/bin"
mkdir -p "${BUILD_DIR}/usr/share/applications"
mkdir -p "${BUILD_DIR}/usr/share/icons/hicolor/512x512/apps"
mkdir -p "${BUILD_DIR}/usr/share/baleno/icons"
mkdir -p "${BUILD_DIR}/usr/share/baleno/vendors"
mkdir -p "${BUILD_DIR}/usr/share/doc/baleno"

# Copy files
echo "Copying application files..."

# Main executable
cp dist/baleno "${BUILD_DIR}/usr/bin/"
chmod 755 "${BUILD_DIR}/usr/bin/baleno"

# Desktop file
cp baleno.desktop "${BUILD_DIR}/usr/share/applications/"

# App Icon
cp assets/baleno.png "${BUILD_DIR}/usr/share/icons/hicolor/512x512/apps/"

# UI Icons
echo "Copying UI icons..."
cp assets/icons/*.svg "${BUILD_DIR}/usr/share/baleno/icons/"

# Vendor Icons
echo "Copying vendor icons..."
cp assets/vendors/*.svg "${BUILD_DIR}/usr/share/baleno/vendors/"

# Documentation
echo "Copying documentation..."
cp README.md "${BUILD_DIR}/usr/share/doc/baleno/"
[ -f LICENSE ] && cp LICENSE "${BUILD_DIR}/usr/share/doc/baleno/copyright"
[ -f docs/INTERFACE.md ] && cp docs/INTERFACE.md "${BUILD_DIR}/usr/share/doc/baleno/"

# Control file
echo "Generating control file..."
cat > "${BUILD_DIR}/DEBIAN/control" <<EOF
Package: ${PKGNAME}
Version: ${VERSION}-${RELEASE}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: Benjamim Gois <benjamimgois@example.com>
Depends: python3 (>= 3.10), python3-pip, python3-pyte, python3-paramiko, picocom, beep, mtr | mtr-tiny, snmp, iw, network-manager, traceroute, whois
Recommends: tigervnc-viewer, freerdp3-wayland | freerdp2-x11
Description: Modern graphical interface for serial communication
 Baleno is a modern and elegant graphical interface for serial
 communication via picocom, with support for SSH and Telnet connections.
 It provides an easy-to-use interface for configuring serial port
 parameters and establishing remote connections.
EOF

# Calculate installed size (in KB)
INSTALLED_SIZE=$(du -s "${BUILD_DIR}/usr" | awk '{print $1}')
echo "Installed-Size: ${INSTALLED_SIZE}" >> "${BUILD_DIR}/DEBIAN/control"

# Post-installation script (if exists)
if [ -f "packaging/debian/postinst" ]; then
    cp "packaging/debian/postinst" "${BUILD_DIR}/DEBIAN/postinst"
    chmod 755 "${BUILD_DIR}/DEBIAN/postinst"
fi

# Build package
echo "Building package..."
dpkg-deb --build "${BUILD_DIR}"

echo ""
echo "=== Package build complete! ==="
echo "Output: build-deb/${PKGNAME}_${VERSION}-${RELEASE}_${ARCH}.deb"
