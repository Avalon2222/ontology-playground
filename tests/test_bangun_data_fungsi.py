"""Tes fungsi pembangun data (scripts/bangun_data.py) dan helper kecil di src/graf.py."""

import csv
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import bangun_data as bd  # noqa: E402
from src import graf  # noqa: E402


@pytest.fixture(scope="module")
def dunia():
    rng = random.Random(42)
    kapal = bd.bangun_kapal(rng)
    pelayaran = bd.bangun_pelayaran(rng, kapal, 60)
    insiden = bd.bangun_insiden(rng, kapal, pelayaran, 15)
    return kapal, pelayaran, insiden


def test_seed_sama_hasil_sama():
    assert bd.bangun_kapal(random.Random(7)) == bd.bangun_kapal(random.Random(7))


def test_kapal_dimiliki_perusahaan_yang_ada(dunia):
    kapal, _, _ = dunia
    id_perusahaan = {p[0] for p in bd.PERUSAHAAN}
    assert len({k[0] for k in kapal}) == len(kapal)
    assert all(k[7] in id_perusahaan for k in kapal)


def test_pelayaran_dan_insiden_merujuk_objek_yang_ada(dunia):
    kapal, pelayaran, insiden = dunia
    id_kapal = {k[0] for k in kapal}
    id_pelabuhan = {p[0] for p in bd.PELABUHAN}
    assert len(pelayaran) == 60
    for v in pelayaran:
        assert v[1] in id_kapal and v[2] in id_pelabuhan and v[3] in id_pelabuhan
        assert v[2] != v[3]
    assert len(insiden) == 15
    assert all(i[1] in id_kapal for i in insiden)


def test_pelayaran_lengkap_pakai_nama_bukan_id(dunia):
    kapal, pelayaran, _ = dunia
    datar = bd.pelayaran_lengkap(kapal, pelayaran)
    assert len(datar) == len(pelayaran)
    assert all(len(b) == len(bd.KOLOM_LENGKAP) for b in datar)
    nama_kapal = {k[1] for k in kapal}
    assert all(b[4] in nama_kapal for b in datar)


def test_tulis_csv_ke_folder_data(tmp_path, monkeypatch):
    monkeypatch.setattr(bd, "DIR_DATA", tmp_path / "data")
    bd.tulis_csv("uji.csv", ["a", "b"], [[1, "x"], [2, "y, z"]])
    with open(tmp_path / "data" / "uji.csv", encoding="utf-8") as f:
        assert list(csv.reader(f)) == [["a", "b"], ["1", "x"], ["2", "y, z"]]


@pytest.mark.parametrize("nilai, kosong", [
    (None, True), (float("nan"), True), ("", True), ("  ", True), ("nan", True),
    (0, False), (0.0, False), ("Balikpapan", False),
])
def test_kosong(nilai, kosong):
    assert graf._kosong(nilai) is kosong
