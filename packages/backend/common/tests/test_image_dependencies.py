"""Guard the image decoder versions used for untrusted avatar uploads."""

import PIL
import pytest
from packaging.version import Version
from PIL import features


# Shared autouse fixtures create the billing catalog even for dependency checks.
pytestmark = pytest.mark.django_db


def test_image_decoder_security_baseline():
    assert Version(PIL.__version__) >= Version('12.3.0')
    # Pillow wheels bundle libwebp; source builds must meet the same security baseline.
    assert features.check('webp')
    assert Version(features.version('webp')) >= Version('1.3.2')
