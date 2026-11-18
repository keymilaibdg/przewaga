"""Tests run on the ETAP 4 defaults unless a test loads a calibration file explicitly."""
import os

os.environ.setdefault("PRZEWAGA_CALIBRATION", "none")
os.environ.setdefault("PRZEWAGA_CUP_RATINGS", "none")
