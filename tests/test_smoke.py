"""Teste mínimo para CI."""


def test_import():
    """O pipeline principal pode ser importado."""
    from src.parameters.nowcasting_parameters import NwcstParams

    params = NwcstParams(source="goes")
    assert params.source == "goes"
    assert len(params.domain) == 4
