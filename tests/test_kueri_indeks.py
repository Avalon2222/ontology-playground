"""Tes indeks entitas dan nilai kategori yang dipakai perencana pertanyaan (src/kueri.py)."""

import shutil

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


def test_indeks_tidak_terbawa_ke_koneksi_baru(tmp_path):
    # Koneksi baru setelah yang lama ditutup sering mendapat id() yang sama; indeksnya harus dibangun ulang.
    shutil.copytree(basis_data.DIR_DATA, tmp_path / "data")
    kapal = tmp_path / "data" / "kapal.csv"
    kapal.write_text(kapal.read_text().replace("MV Celebes Sentosa 8", "MV Garuda Uji Coba", 1))

    for _ in range(5):
        lama = basis_data.buat_koneksi()
        kueri.indeks_entitas(lama)
        lama.close()
        del lama
        baru = basis_data.buat_koneksi(tmp_path / "data")
        teks = {t for t, *_ in kueri.indeks_entitas(baru)}
        assert "garuda uji coba" in teks
        baru.close()
        del baru


def test_nilai_kategori_tidak_terbawa_ke_koneksi_baru(tmp_path):
    shutil.copytree(basis_data.DIR_DATA, tmp_path / "data")
    kapal = tmp_path / "data" / "kapal.csv"
    kapal.write_text(kapal.read_text().replace(",ro-ro,", ",kapal penumpang,"))

    for _ in range(5):
        lama = basis_data.buat_koneksi()
        kueri.nilai_kategori(lama)
        lama.close()
        del lama
        baru = basis_data.buat_koneksi(tmp_path / "data")
        nilai = {v for v, *_ in kueri.nilai_kategori(baru)}
        assert "kapal penumpang" in nilai
        baru.close()
        del baru


def test_filter_kategori_bertanda_baca_tetap_menemukan_objek(tmp_path):
    shutil.copytree(basis_data.DIR_DATA, tmp_path / "data")
    kapal = tmp_path / "data" / "kapal.csv"
    kapal.write_text(kapal.read_text().replace(",ro-ro,", ",kapal (penumpang),"))
    kon = basis_data.buat_koneksi(tmp_path / "data")
    f, _ = kueri.kenali_filter(kon, kueri._normal("kapal (penumpang)"), {"kapal"})
    f = [x for x in f if x.kolom == "jenis"]
    assert f and f[0].nilai == "kapal (penumpang)"
    sql, params = kueri._syarat_filter(f[0], "k")
    assert kon.execute(f"SELECT COUNT(*) FROM kapal k WHERE {sql}", params).fetchone()[0] > 0
    kon.close()
