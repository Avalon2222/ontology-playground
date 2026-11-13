"""Tes indeks entitas dan nilai kategori yang dipakai perencana pertanyaan (src/kueri.py)."""

import pytest

from src import basis_data, kueri


@pytest.fixture(scope="module")
def kon():
    return basis_data.buat_koneksi()


@pytest.mark.parametrize("masuk, keluar", [
    ("Kapal dari Balikpapan?", "kapal dari balikpapan"),
    ("muatan 80.000 ton, 5,5 juta", "muatan 80.000 ton 5,5 juta"),
    ('PT "Nusantara" (Persero)!', "pt nusantara persero"),
    ("   banyak    spasi   ", "banyak spasi"),
])
def test_normal_rapikan_tanda_baca_tapi_jaga_angka(masuk, keluar):
    assert kueri._normal(masuk) == keluar


def test_indeks_entitas_terpanjang_dahulu_dan_dicache(kon):
    indeks = kueri.indeks_entitas(kon)
    panjang = [len(teks) for teks, *_ in indeks]
    assert panjang == sorted(panjang, reverse=True)
    assert kueri.indeks_entitas(kon) is indeks


def test_indeks_entitas_tanpa_nama_terlalu_umum(kon):
    teks = {t for t, *_ in kueri.indeks_entitas(kon)}
    assert not teks & kueri.STOP_ENTITAS
    assert all(len(t) >= 3 for t in teks)
    # Varian tanpa awalan "PT " ikut terdaftar supaya pertanyaan santai tetap dikenali.
    assert all(not t.startswith("pt ") or t[3:] in teks for t in teks)


def test_nilai_kategori_terpanjang_dahulu(kon):
    nilai = kueri.nilai_kategori(kon)
    assert nilai, "basis data harus punya properti kategori"
    panjang = [len(v) for v, *_ in nilai]
    assert panjang == sorted(panjang, reverse=True)
    assert all(v == v.lower() for v, *_ in nilai)


def test_nama_tanpa_pt_dan_persero_tetap_dikenali(kon):
    entitas, _ = kueri.kenali_entitas(kon, "kapal milik pelabuhan indonesia")
    assert any("Pelabuhan Indonesia" in e.nama for e in entitas)
