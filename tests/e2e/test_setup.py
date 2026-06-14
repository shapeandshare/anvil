"""e2e setup test."""


def test_import_anvil():
    import anvil

    assert anvil.__version__ == "0.1.0"


def test_import_core():
    from anvil.core import engine

    assert engine is not None
