import json

LCC_BYTES = json.dumps(
    {
        "meta": {"file_type": "LeathercraftCAD"},
        "layers": [{"id": 0, "nam": "Outer Shell"}, {"id": 1, "nam": "Inner Shell"}],
        "shapes": [
            {"gid": "1", "sp": [0, 0], "ep": [100, 0]},
            {"gid": "1", "sp": [100, 0], "ep": [100, 50]},
            {"gid": "2", "sp": [0, 60], "ep": [100, 60]},
        ],
    }
).encode("utf-8")


def _upload(client, filename="Classic_Trifold_-_Copy.lcc", **form):
    files = {"pattern_file": (filename, LCC_BYTES, "application/octet-stream")}
    data = {"name": "", "category": "", "tags": "", "notes": "", **form}
    return client.post("/patterns", files=files, data=data)


def test_library_starts_empty(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "No patterns yet" in resp.text


def test_uploading_a_pattern_redirects_to_its_detail_page(client):
    resp = _upload(client)
    assert resp.status_code == 200  # TestClient follows the 303 redirect
    assert "Classic Trifold" in resp.text  # derived from the filename
    assert "Outer Shell" in resp.text
    assert "Inner Shell" in resp.text


def test_rejects_an_unsupported_file_type(client):
    files = {"pattern_file": ("notes.txt", b"hello", "text/plain")}
    resp = client.post("/patterns", files=files, data={"name": "", "category": "", "tags": "", "notes": ""})
    assert resp.status_code == 400


def test_explicit_name_overrides_the_filename_derived_one(client):
    resp = _upload(client, name="My Wallet")
    assert "My Wallet" in resp.text
    assert "Classic Trifold" not in resp.text


def test_uploaded_pattern_appears_in_the_library_and_api(client):
    _upload(client)
    page = client.get("/")
    assert "Classic Trifold" in page.text

    api = client.get("/api/patterns").json()
    assert len(api) == 1
    assert api[0]["name"] == "Classic Trifold"
    assert api[0]["shape_count"] == 2


def test_search_filters_by_name(client):
    _upload(client, name="Trifold Wallet")
    _upload(client, name="Bifold Wallet", filename="Classic_Bifold.lcc")

    assert len(client.get("/api/patterns?q=Trifold").json()) == 1
    assert len(client.get("/api/patterns?q=Wallet").json()) == 2
    assert len(client.get("/api/patterns?q=nonexistent").json()) == 0


def test_tag_filter_matches_a_whole_tag_not_a_substring(client):
    _upload(client, tags="bifold, veg-tan")
    _upload(client, name="Other", filename="Other.lcc", tags="bi")

    assert len(client.get("/api/patterns?tag=bifold").json()) == 1
    assert len(client.get("/api/patterns?tag=bi").json()) == 1


def test_editing_a_pattern_updates_its_metadata(client):
    _upload(client)
    pattern_id = client.get("/api/patterns").json()[0]["id"]

    resp = client.post(
        f"/patterns/{pattern_id}/edit",
        data={"name": "Renamed", "category": "Wallet", "tags": "renamed", "notes": "updated"},
    )
    assert resp.status_code == 200
    assert "Renamed" in resp.text
    assert "updated" in resp.text


def test_deleting_a_pattern_removes_it_from_the_library(client):
    _upload(client)
    pattern_id = client.get("/api/patterns").json()[0]["id"]

    resp = client.post(f"/patterns/{pattern_id}/delete")
    assert resp.status_code == 200
    assert client.get("/api/patterns").json() == []
    assert client.get(f"/patterns/{pattern_id}").status_code == 404


def test_downloading_the_original_returns_the_exact_bytes_uploaded(client):
    _upload(client)
    pattern_id = client.get("/api/patterns").json()[0]["id"]

    resp = client.get(f"/patterns/{pattern_id}/download/original")
    assert resp.status_code == 200
    assert resp.content == LCC_BYTES


def test_pdf_download_404s_when_no_pdf_was_attached(client):
    _upload(client)
    pattern_id = client.get("/api/patterns").json()[0]["id"]
    assert client.get(f"/patterns/{pattern_id}/download/pdf").status_code == 404
