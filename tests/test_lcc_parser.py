import json

from app.lcc_parser import parse_lcc_summary


def _lcc(layers, shapes):
    return json.dumps(
        {"meta": {"file_type": "LeathercraftCAD"}, "layers": layers, "shapes": shapes}
    ).encode("utf-8")


def test_named_layers_are_kept_and_default_ones_are_dropped():
    raw = _lcc(
        layers=[
            {"id": 0, "nam": "Outer Shell"},
            {"id": 1, "nam": "Layer 2"},
            {"id": 2, "nam": "Inner Shell"},
        ],
        shapes=[],
    )
    summary = parse_lcc_summary(raw)
    assert summary.layer_names == ["Outer Shell", "Inner Shell"]


def test_shape_count_counts_distinct_groups_not_individual_lines():
    raw = _lcc(
        layers=[],
        shapes=[
            {"gid": "1", "sp": [0, 0], "ep": [10, 0]},
            {"gid": "1", "sp": [10, 0], "ep": [10, 10]},
            {"gid": "2", "sp": [20, 20], "ep": [30, 20]},
        ],
    )
    summary = parse_lcc_summary(raw)
    assert summary.shape_count == 2


def test_canvas_size_is_the_bounding_box_of_every_point():
    raw = _lcc(
        layers=[],
        shapes=[
            {"gid": "1", "sp": [-10, 5], "ep": [40, 5]},
            {"gid": "1", "sp": [40, 5], "ep": [40, 95]},
        ],
    )
    summary = parse_lcc_summary(raw)
    assert summary.canvas_w_mm == 50
    assert summary.canvas_h_mm == 90


def test_empty_pattern_has_no_canvas_size():
    raw = _lcc(layers=[], shapes=[])
    summary = parse_lcc_summary(raw)
    assert summary.canvas_w_mm is None
    assert summary.canvas_h_mm is None
    assert summary.shape_count == 0


def test_handles_the_utf8_bom_leathercraftcad_actually_writes():
    # Real .lcc files out of LeathercraftCAD start with a UTF-8 BOM, which
    # plain json.loads(bytes.decode("utf-8")) rejects outright.
    raw = b"\xef\xbb\xbf" + _lcc(layers=[{"id": 0, "nam": "Outer Shell"}], shapes=[])
    summary = parse_lcc_summary(raw)
    assert summary.layer_names == ["Outer Shell"]
