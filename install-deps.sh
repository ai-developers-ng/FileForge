#!/usr/bin/env bash
# ============================================================================
# FileForge - System Dependency Installer
# Supports: Ubuntu/Debian, RHEL 8/CentOS 8/Alma 8, macOS (Homebrew)
# ============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# --------------------------------------------------------------------------
# Detect OS
# --------------------------------------------------------------------------
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    elif [[ -f /etc/os-release ]]; then
        . /etc/os-release
        case "$ID" in
            ubuntu|debian)  OS="ubuntu" ;;
            rhel|centos|almalinux|rocky) OS="rhel" ;;
            *)
                error "Unsupported Linux distribution: $ID"
                error "Supported: ubuntu, debian, rhel, centos, almalinux, rocky"
                exit 1
                ;;
        esac
    else
        error "Cannot detect operating system."
        exit 1
    fi
    info "Detected OS: $OS"
}

# --------------------------------------------------------------------------
# Ubuntu / Debian
# --------------------------------------------------------------------------
install_ubuntu() {
    info "Updating apt package index..."
    sudo apt-get update -y

    info "Installing system dependencies..."
    sudo apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        gcc \
        libffi-dev \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-fra \
        tesseract-ocr-deu \
        tesseract-ocr-spa \
        tesseract-ocr-ita \
        tesseract-ocr-por \
        tesseract-ocr-nld \
        tesseract-ocr-rus \
        tesseract-ocr-chi-sim \
        tesseract-ocr-chi-tra \
        tesseract-ocr-jpn \
        tesseract-ocr-kor \
        tesseract-ocr-ara \
        tesseract-ocr-hin \
        tesseract-ocr-tur \
        imagemagick \
        libmagickwand-dev \
        ghostscript \
        ffmpeg \
        poppler-utils \
        libmagic1 \
        pandoc \
        texlive-latex-base \
        texlive-latex-recommended \
        texlive-fonts-recommended \
        lmodern \
        wget \
        curl

    # Configure ImageMagick policy to allow PDF operations
    local policy_file="/etc/ImageMagick-6/policy.xml"
    if [[ -f "$policy_file" ]]; then
        info "Configuring ImageMagick to allow PDF operations..."
        sudo sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' "$policy_file" || true
    fi

    ok "Ubuntu/Debian dependencies installed."
}

# --------------------------------------------------------------------------
# RHEL 8 / CentOS 8 / Alma 8 / Rocky 8
# --------------------------------------------------------------------------
install_rhel() {
    info "Enabling EPEL and PowerTools/CRB repositories..."
    sudo dnf install -y epel-release

    # RHEL 8 uses "powertools", RHEL 9+ uses "crb"
    if sudo dnf repolist --all 2>/dev/null | grep -qi powertools; then
        sudo dnf config-manager --set-enabled powertools || true
    elif sudo dnf repolist --all 2>/dev/null | grep -qi crb; then
        sudo dnf config-manager --set-enabled crb || true
    fi

    info "Installing base system dependencies..."
    sudo dnf install -y \
        python3 \
        python3-pip \
        python3-devel \
        gcc \
        libffi-devel \
        ImageMagick \
        ImageMagick-devel \
        ghostscript \
        ffmpeg-free \
        poppler-utils \
        file-libs \
        wget \
        curl \
        texlive-scheme-basic \
        texlive-collection-fontsrecommended \
        texlive-lm

    # ---------- Tesseract OCR ----------
    info "Installing Tesseract OCR..."
    sudo dnf install -y tesseract

    info "Installing Tesseract language packs..."
    # RHEL/EPEL package names use tesseract-langpack-<code>
    local langs=(
        eng fra deu spa ita por nld rus
        chi_sim chi_tra jpn kor ara hin tur
    )
    for lang in "${langs[@]}"; do
        sudo dnf install -y "tesseract-langpack-${lang}" 2>/dev/null || \
            warn "Language pack tesseract-langpack-${lang} not found in repos (install manually if needed)."
    done

    # ---------- Pandoc ----------
    info "Installing Pandoc..."
    if ! command -v pandoc &>/dev/null; then
        local pandoc_version="3.1.11"
        local arch
        arch=$(uname -m)
        if [[ "$arch" == "x86_64" ]]; then
            arch="amd64"
        elif [[ "$arch" == "aarch64" ]]; then
            arch="arm64"
        fi
        local pandoc_url="https://github.com/jgm/pandoc/releases/download/${pandoc_version}/pandoc-${pandoc_version}-linux-${arch}.tar.gz"
        info "Downloading Pandoc ${pandoc_version} for ${arch}..."
        wget -q "$pandoc_url" -O /tmp/pandoc.tar.gz
        sudo tar xzf /tmp/pandoc.tar.gz -C /usr/local --strip-components=1
        rm -f /tmp/pandoc.tar.gz
        ok "Pandoc ${pandoc_version} installed."
    else
        ok "Pandoc already installed: $(pandoc --version | head -1)"
    fi

    # ---------- FFmpeg (if ffmpeg-free was not available) ----------
    if ! command -v ffmpeg &>/dev/null; then
        warn "ffmpeg-free was not found. Trying RPM Fusion..."
        sudo dnf install -y \
            "https://mirrors.rpmfusion.org/free/el/rpmfusion-free-release-8.noarch.rpm" 2>/dev/null || true
        sudo dnf install -y ffmpeg --allowerasing 2>/dev/null || \
            warn "FFmpeg could not be installed. Install it manually from RPM Fusion."
    fi

    # Configure ImageMagick policy
    local policy_file="/etc/ImageMagick-6/policy.xml"
    if [[ -f "$policy_file" ]]; then
        info "Configuring ImageMagick to allow PDF operations..."
        sudo sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' "$policy_file" || true
    fi

    ok "RHEL 8 dependencies installed."
}

# --------------------------------------------------------------------------
# macOS (Homebrew)
# --------------------------------------------------------------------------
install_macos() {
    # Check for Homebrew
    if ! command -v brew &>/dev/null; then
        error "Homebrew is not installed. Install it from https://brew.sh"
        exit 1
    fi

    info "Updating Homebrew..."
    brew update

    info "Installing system dependencies..."
    brew install \
        python@3.13 \
        tesseract \
        imagemagick \
        ghostscript \
        ffmpeg \
        poppler \
        pandoc \
        libmagic

    # Install Tesseract language packs (all bundled in tesseract formula with --with-all-languages)
    info "Installing Tesseract language data..."
    brew install tesseract-lang

    # Install a LaTeX distribution for PDF generation
    info "Ensuring full TeX distribution (mactex-no-gui) for PDF generation..."
    if ! command -v pdflatex &>/dev/null || ! kpsewhich lualatex-math.sty &>/dev/null; then
        brew install --cask mactex-no-gui
        # Add TeX to PATH for current session
        eval "$(/usr/libexec/path_helper)"
        warn "MacTeX installed/updated. You may need to restart your terminal or run:"
        warn "  eval \"\$(/usr/libexec/path_helper)\""
    fi

    if command -v pdflatex &>/dev/null; then
        ok "LaTeX available: $(pdflatex --version | head -1)"
    else
        warn "pdflatex still not found on PATH. Open a new shell and rerun verification."
    fi

    ok "macOS dependencies installed."
    info "Note: Set MAGICK_HOME=/opt/homebrew (Apple Silicon) or /usr/local (Intel) for Wand."
}

# --------------------------------------------------------------------------
# Install Python dependencies
# --------------------------------------------------------------------------
install_python_deps() {
    info "Installing Python dependencies from requirements.txt..."

    local req_file
    req_file="$(cd "$(dirname "$0")" && pwd)/requirements.txt"

    if [[ ! -f "$req_file" ]]; then
        warn "requirements.txt not found at $req_file"
        warn "Run 'pip install -r requirements.txt' manually from the project directory."
        return
    fi

    if [[ -n "${VIRTUAL_ENV:-}" ]]; then
        info "Virtual environment detected: $VIRTUAL_ENV"
        pip install -r "$req_file"
    else
        warn "No virtual environment detected. Installing with --user flag."
        warn "Consider creating a venv first: python3 -m venv venv && source venv/bin/activate"
        pip3 install --user -r "$req_file"
    fi

    ok "Python dependencies installed."
}

# --------------------------------------------------------------------------
# Verify installations
# --------------------------------------------------------------------------
verify() {
    echo ""
    info "Verifying installations..."
    echo "-------------------------------------------"

    local all_ok=true

    for cmd in python3 tesseract magick ffmpeg pandoc pdftotext pdflatex; do
        if command -v "$cmd" &>/dev/null; then
            ok "$cmd  ->  $(command -v "$cmd")"
        else
            # magick vs convert (ImageMagick 6 vs 7)
            if [[ "$cmd" == "magick" ]] && command -v convert &>/dev/null; then
                ok "convert (ImageMagick 6)  ->  $(command -v convert)"
            else
                warn "$cmd  ->  NOT FOUND"
                all_ok=false
            fi
        fi
    done

    # Check python-magic / libmagic
    if python3 -c "import magic; magic.from_file('/dev/null', mime=True)" &>/dev/null; then
        ok "python-magic (libmagic)  ->  working"
    else
        warn "python-magic (libmagic)  ->  NOT WORKING"
        all_ok=false
    fi

    echo "-------------------------------------------"
    if $all_ok; then
        ok "All dependencies verified successfully!"
    else
        warn "Some dependencies are missing. See warnings above."
    fi
}

# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
main() {
    echo "============================================"
    echo "  FileForge - Dependency Installer"
    echo "============================================"
    echo ""

    detect_os

    case "$OS" in
        ubuntu)  install_ubuntu ;;
        rhel)    install_rhel   ;;
        macos)   install_macos  ;;
    esac

    install_python_deps
    verify

    echo ""
    ok "Done! FileForge dependencies are installed."
    info "Start the app with: python app.py"
}

main "$@"
