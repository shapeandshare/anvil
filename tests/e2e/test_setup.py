"""e2e setup test."""


def test_import_microgpt():
    import microgpt

    assert microgpt.__version__ == "0.1.0"


def test_import_core():
    from microgpt.core import engine

    assert engine is not None
