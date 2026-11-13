"""Tes pemilihan jalur dan penyusunan SQL di src/kueri.py."""

import pytest

from src import basis_data, kueri


def _id_tautan(hasil):
    jalur, tautan = hasil
    return jalur, [[l.id for l in langkah] for langkah in tautan]


@pytest.mark.parametrize("petunjuk, tautan", [
    ("pelayaran dari", "pelayaran_berangkat_dari"),
    ("pelayaran ke", "pelayaran_tiba_di"),
])
def test_pilih_jalur_kata_dari_dan_ke(petunjuk, tautan):
    jalur, langkah = _id_tautan(kueri.pilih_jalur("pelayaran", "pelabuhan", petunjuk + " dumai", set(), petunjuk))
    assert jalur == ["pelayaran", "pelabuhan"]
    assert langkah == [[tautan]]


def test_pilih_jalur_petunjuk_lokal_lebih_dipercaya():
    # Kalimat memuat "dari" dan "ke"; yang menentukan adalah kata tepat sebelum entitas.
    teks = "pelayaran dari dumai ke mundra"
    _, langkah = _id_tautan(kueri.pilih_jalur("pelayaran", "pelabuhan", teks, set(), "dumai ke"))
    assert langkah == [["pelayaran_tiba_di"]]


@pytest.fixture(scope="module")
def kon():
    return basis_data.buat_koneksi()


def test_susun_sql_pakai_parameter_bukan_teks_entitas(kon):
    r = kueri.rencanakan(kon, "kapal milik Nusantara Bulk")
    assert r.sql and r.params
    # Nama/id entitas dikirim sebagai parameter, tidak ditempel ke SQL (aman dari injeksi).
    assert "nusantara" not in r.sql.lower() and "pt_nbc" not in r.sql
    assert r.sql.count("?") == len(r.params)


def test_susun_sql_hasil_bisa_dijalankan_dan_hanya_select(kon):
    r = kueri.rencanakan(kon, "pelayaran dari Dumai")
    assert r.sql.lstrip().upper().startswith(("SELECT", "WITH"))
    df, _ = kueri.jalankan(kon, r)
    assert not df.empty
