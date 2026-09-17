# Maintainer: Benjamim Gois <benjamimgois@example.com>
pkgname=baleno
pkgver=1.9
pkgrel=1
pkgdesc="Modern graphical interface for network device management"
arch=('any')
url="https://github.com/benjamimgois/opengrid"
license=('GPL3')
makedepends=('python-build' 'python-installer' 'python-setuptools' 'python-wheel')
depends=(
    'python'
    'python-pyqt6'
    'python-pyqt6-serialport'
    'python-pyte'
    'python-paramiko'
    'python-pysnmp'
    'picocom'
    'openssh'
    'samba'
    'iperf3'
    'traceroute'
    'mtr'
    'networkmanager'
    'nmap'
    'iw'
)
optdepends=(
    'tigervnc: VNC viewer'
    'freerdp: RDP client'
    'python-pyftpdlib: built-in FTP server'
)
source=("$pkgname-$pkgver.tar.gz::https://github.com/benjamimgois/opengrid/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')

build() {
    cd "opengrid-$pkgver"
    python -m build --wheel --no-isolation
}

package() {
    cd "opengrid-$pkgver"
    python -m installer --destdir="$pkgdir" dist/*.whl

    install -Dm644 baleno.desktop "$pkgdir/usr/share/applications/baleno.desktop"
    install -Dm644 assets/icons/baleno_icon.svg "$pkgdir/usr/share/icons/hicolor/scalable/apps/baleno.svg"
    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"

    # Application assets expected at runtime
    install -Dm644 assets/photo.png "$pkgdir/usr/share/baleno/photo.png"
    install -dm755 "$pkgdir/usr/share/baleno/icons"
    install -Dm644 assets/icons/*.svg "$pkgdir/usr/share/baleno/icons/"
    install -Dm644 assets/icons/*.png "$pkgdir/usr/share/baleno/icons/" 2>/dev/null || true
    install -dm755 "$pkgdir/usr/share/baleno/vendors"
    install -Dm644 assets/vendors/*.svg "$pkgdir/usr/share/baleno/vendors/"
}
