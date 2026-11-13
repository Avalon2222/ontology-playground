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
