"""Data hasil generator harus deterministik dan mematuhi aturan dunianya sendiri."""

import filecmp
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import bangun_data  # noqa: E402

DATA = ROOT / "data"


def baca(nama):
    return pd.read_csv(DATA / f"{nama}.csv", dtype=str, keep_default_na=False)


def test_generator_deterministik(tmp_path, monkeypatch):
    monkeypatch.setattr(bangun_data, "DIR_DATA", tmp_path)
    monkeypatch.setattr(sys, "argv", ["bangun_data.py"])
    bangun_data.main()
    for f in sorted(tmp_path.glob("*.csv")):
        assert filecmp.cmp(f, DATA / f.name, shallow=False), f"{f.name} berbeda dari data/ yang di-commit"


def test_pelayaran_konsisten():
    v = baca("pelayaran")
    k = baca("kapal").set_index("id")
    p = baca("pelabuhan").set_index("id")
    kom = baca("komoditas").set_index("id")
    assert (pd.to_datetime(v["tiba"]) >= pd.to_datetime(v["berangkat"])).all()
    for _, r in v.iterrows():
        kapal = k.loc[r["kapal_id"]]
        assert bangun_data.JENIS_KAPAL[kom.loc[r["komoditas_id"], "moda"]] == kapal["jenis"]
        domestik = p.loc[r["asal_id"], "negara"] == "Indonesia" and p.loc[r["tujuan_id"], "negara"] == "Indonesia"
        if domestik:
            assert kapal["bendera"] == "Indonesia", "cabotage: rute domestik hanya kapal berbendera Indonesia"
        tiba, berangkat = date.fromisoformat(r["tiba"]), date.fromisoformat(r["berangkat"])
        status = "selesai" if tiba <= bangun_data.HARI_INI else ("berlayar" if berangkat <= bangun_data.HARI_INI else "dijadwalkan")
        assert r["status"] == status
        assert r["asal_id"] != r["tujuan_id"]


def test_insiden_merujuk_pelayaran_kapal_yang_sama():
    i = baca("insiden")
    v = baca("pelayaran").set_index("id")
    for _, r in i.iterrows():
        pel = v.loc[r["pelayaran_id"]]
        assert pel["kapal_id"] == r["kapal_id"]
        assert r["pelabuhan_id"] in (pel["asal_id"], pel["tujuan_id"])
        assert r["tingkat"] == bangun_data.TINGKAT_INSIDEN[r["jenis"]]
        assert date.fromisoformat(r["tanggal"]) <= bangun_data.HARI_INI


def test_kapal_asing_milik_perusahaan_asing():
    k = baca("kapal")
    p = baca("perusahaan").set_index("id")
    for _, r in k.iterrows():
        asing = p.loc[r["pemilik_id"], "kepemilikan"] == "asing"
        assert (r["bendera"] != "Indonesia") == asing or (not asing and r["bendera"] == "Singapura")
        dwt_min, dwt_max = bangun_data.DWT_RENTANG[r["jenis"]]
        assert dwt_min <= int(r["dwt"]) <= dwt_max


def test_referensi_nyata_lengkap():
    assert len(baca("provinsi")) == 38
    pel = baca("pelabuhan")
    assert (pel["negara"] == "Indonesia").sum() == 30 and pel["id"].str.len().eq(5).all()
    assert (pel.loc[pel["negara"] == "Indonesia", "provinsi_id"] != "").all()
    assert (pel.loc[pel["negara"] != "Indonesia", "provinsi_id"] == "").all()
    kp = baca("komoditas_provinsi")
    assert set(kp["komoditas_id"]) == set(baca("komoditas")["id"])


@pytest.mark.parametrize("pasangan", [((-6.1, 106.9), (1.26, 103.84), 880, 920)])
def test_haversine(pasangan):
    (a, b), (c, d), bawah, atas = pasangan
    assert bawah <= bangun_data.haversine_km(a, b, c, d) <= atas
