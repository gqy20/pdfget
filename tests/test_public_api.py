import pdfget


def test_unified_input_facades_are_exported():
    assert pdfget.download_from_unified_input is not None
    assert pdfget.build_download_plan_from_unified_input is not None
    assert "download_from_unified_input" in pdfget.__all__
    assert "build_download_plan_from_unified_input" in pdfget.__all__
