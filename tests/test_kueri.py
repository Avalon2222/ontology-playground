"""Perencana pertanyaan: entitas, tipe target, maksud, jalur, SQL yang bisa dijalankan, kalimat jawaban."""

import pytest

from src import basis_data, kueri


@pytest.fixture(scope="module")
def kon():
    return basis_data.buat_koneksi()


def rencana(kon, q):
    r = kueri.rencanakan(kon, q)
    df, kalimat = kueri.jalankan(kon, r)
    return r, df, kalimat


def jangkar(r):
    return [(e.tipe, e.id) for e in r.jangkar]


def test_entitas_nama_alias_dan_id(kon):
    e, sisa = kueri.kenali_entitas(kon, kueri._normal("pelayaran dari Kaltim ke Priok dengan KPL-057"))
    assert [(x.tipe, x.id) for x in e] == [("provinsi", "ID-KI"), ("pelabuhan", "IDJKT"), ("kapal", "KPL-057")]
    assert "kaltim" not in sisa and "pelayaran" in sisa


def test_entitas_terpanjang_menang(kon):
    e, _ = kueri.kenali_entitas(kon, "kapal nusantara bulk carriers")
    assert [(x.tipe, x.id) for x in e] == [("perusahaan", "pt_nbc")]


def test_daftar_kapal_milik_perusahaan(kon):
    r, df, kalimat = rencana(kon, "Kapal apa saja yang dimiliki Nusantara Bulk Carriers?")
    assert r.maksud == "daftar" and r.tipe_target == "kapal" and jangkar(r) == [("perusahaan", "pt_nbc")]
    assert (df["pemilik_id"] == "pt_nbc").all() and len(df) == 7
    assert "7 kapal" in kalimat


def test_kata_tipe_sebelum_entitas_bukan_target(kon):
    r, df, _ = rencana(kon, "berapa insiden kapal Celebes Sentosa 8")
    assert r.maksud == "hitung" and r.tipe_target == "insiden" and jangkar(r) == [("kapal", "KPL-001")]
    assert int(df.iloc[0]["jumlah"]) == 3


def test_pelabuhan_di_provinsi(kon):
    r, df, _ = rencana(kon, "Pelabuhan di Kalimantan Timur")
    assert r.tipe_target == "pelabuhan" and r.jalur == [["pelabuhan", "provinsi"]]
    assert set(df["id"]) == {"IDBPN", "IDSRI"}


def test_dari_dan_ke_memilih_tautan_berbeda(kon):
    r, df, _ = rencana(kon, "pelayaran ke Shanghai dari Bitung")
    label = {e.id: [l.id for l in tautan[-1]] for e, tautan in zip(r.jangkar, r.tautan_jalur)}
    assert label["CNSHA"] == ["pelayaran_tiba_di"] and label["IDBIT"] == ["pelayaran_berangkat_dari"]
    assert (df["asal_id"] == "IDBIT").all() and (df["tujuan_id"] == "CNSHA").all()


def test_dua_pelabuhan_tanpa_kata_benda_berarti_pelayaran(kon):
    r, _, _ = rencana(kon, "Dumai ke Mundra")
    assert r.tipe_target == "pelayaran" and len(r.jangkar) == 2


def test_hitung_dengan_tahun(kon):
    r, df, kalimat = rencana(kon, "Berapa pelayaran yang tiba di Tanjung Priok tahun 2025?")
    assert r.maksud == "hitung" and [f.operator for f in r.filter] == ["tahun"]
    assert r.tautan_jalur[0][0][0].id == "pelayaran_tiba_di"
    n = kon.execute("SELECT COUNT(*) FROM pelayaran WHERE tujuan_id='IDJKT' AND berangkat LIKE '2025%'").fetchone()[0]
    assert int(df.iloc[0]["jumlah"]) == n and "Total muatan" in kalimat


def test_peringkat_pelabuhan_tersibuk(kon):
    r, df, kalimat = rencana(kon, "Pelabuhan mana yang paling banyak pelayaran?")
    assert r.maksud == "peringkat" and r.tipe_target == "pelabuhan" and r.tipe_ukur == "pelayaran"
    assert df["jumlah"].is_monotonic_decreasing and len(df) == kueri.BATAS_PERINGKAT
    assert "terbanyak" in kalimat


def test_peringkat_target_dari_kata_tanya(kon):
    r, df, _ = rencana(kon, "insiden terbanyak kapal mana")
    assert r.tipe_target == "kapal" and r.tipe_ukur == "insiden"
    terbanyak = kon.execute("SELECT kapal_id, COUNT(*) n FROM insiden GROUP BY kapal_id ORDER BY n DESC LIMIT 1").fetchone()
    assert df.iloc[0]["id"] == terbanyak[0] and int(df.iloc[0]["jumlah"]) == terbanyak[1]


def test_ekstrem_properti(kon):
    r, df, _ = rencana(kon, "kapal terbesar")
    assert r.maksud == "ekstrem" and r.urut == ("dwt", "DESC") and df["dwt"].is_monotonic_decreasing
    r, df, _ = rencana(kon, "provinsi terpadat")
    assert df.iloc[0]["id"] == "ID-JB"


def test_filter_kategori_dan_bendera_asing(kon):
    r, df, _ = rencana(kon, "Kapal berbendera asing mana yang mengangkut nikel?")
    assert jangkar(r) == [("komoditas", "nikel")] and (df["bendera"] != "Indonesia").all() and len(df) > 0
    r, df, _ = rencana(kon, "berapa kapal tanker")
    assert [f.nilai for f in r.filter] == ["tanker"] and int(df.iloc[0]["jumlah"]) == 13


def test_pivot_keberadaan_tanpa_nama(kon):
    r, df, _ = rencana(kon, "Kapal tertua yang pernah mengalami insiden tingkat tinggi")
    assert r.maksud == "ekstrem" and jangkar(r) == [("insiden", "")]
    assert any(f.kolom == "tingkat" and f.nilai == "tinggi" for f in r.filter)
    ada = {k for (k,) in kon.execute("SELECT DISTINCT kapal_id FROM insiden WHERE tingkat='tinggi'")}
    assert set(df["id"]) <= ada and df["tahun_dibangun"].is_monotonic_increasing


def test_tautan_diri_sendiri_arah(kon):
    _, df, _ = rencana(kon, "Anak usaha Khatulistiwa Group")
    assert set(df["id"]) == {"pt_skl", "pt_bauksit"}
    _, df, _ = rencana(kon, "induk dari Nusantara Bulk Carriers")
    assert df["id"].tolist() == ["nmh"]


def test_perbandingan_angka(kon):
    r, df, _ = rencana(kon, "kapal lebih dari 80 ribu dwt")
    assert r.filter[0].operator == ">=" and (df["dwt"] >= 80000).all() and len(df) > 0


def test_detail_dan_bantuan(kon):
    r = kueri.rencanakan(kon, "Tanjung Priok")
    assert r.maksud == "detail" and jangkar(r) == [("pelabuhan", "IDJKT")]
    r = kueri.rencanakan(kon, "halo apa kabar")
    assert r.maksud == "bantuan"


def test_konteks_pertanyaan_sebelumnya(kon):
    r1 = kueri.rencanakan(kon, "kapal milik Meridian")
    r2 = kueri.rencanakan(kon, "komoditas yang ditangani perusahaan itu", konteks=r1.jangkar)
    assert jangkar(r2) == [("perusahaan", "meridian")] and r2.tipe_target == "komoditas"
    _, df, _ = rencana(kon, "komoditas yang ditangani Meridian")
    assert set(df["id"]) == {"batu_bara", "nikel", "cpo", "minyak_mentah"}


@pytest.mark.parametrize("q", kueri.CONTOH_PERTANYAAN)
def test_semua_contoh_bisa_dijalankan(kon, q):
    r, df, kalimat = rencana(kon, q)
    assert r.maksud != "bantuan"
    if r.maksud != "detail":
        assert r.sql.lstrip().upper().startswith("SELECT") and kalimat
        assert len(r.penjelasan) >= 1


def test_sql_hanya_membaca(kon):
    r = kueri.rencanakan(kon, "kapal milik Meridian")
    assert "DELETE" not in r.sql.upper() and r.params == ["meridian"]


@pytest.mark.parametrize("q, kolom, nilai", [
    ("kapal lebih dari 80.000 dwt", "dwt", 80_000),               # titik ribuan
    ("kapal di atas 80 ribu dwt", "dwt", 80_000),
    ("provinsi dengan penduduk lebih dari 5,5 juta", "penduduk_juta", 5.5),   # koma desimal + satuan juta
    ("provinsi dengan penduduk di bawah 2 juta", "penduduk_juta", 2),
])
def test_angka_gaya_indonesia(kon, q, kolom, nilai):
    r, df, _ = rencana(kon, q)
    f = [f for f in r.filter if f.kolom == kolom][0]
    assert float(f.nilai) == pytest.approx(nilai)
    assert len(df) > 0


def test_angka_parser():
    assert kueri._angka("1.250.000", None) == 1_250_000
    assert kueri._angka("2,75", "ribu") == pytest.approx(2_750)
    assert kueri._angka("1.5", None) == 1.5
    assert kueri._normal("Kapal 80.000 DWT, tahun 2015.") == "kapal 80.000 dwt tahun 2015"


def test_kenali_tipe_urut_posisi_tanpa_duplikat():
    t = kueri.kenali_tipe("kapal mana yang mengangkut komoditas ke pelabuhan")
    assert [(pos, tipe) for pos, tipe, _ in t] == [(0, "kapal"), (4, "komoditas"), (6, "pelabuhan")]


def test_kenali_tipe_teks_kosong():
    assert kueri.kenali_tipe("") == []
    assert kueri.kenali_tipe("   ") == []


def test_kenali_tipe_tidak_cocok_di_tengah_kata():
    # "portal" tidak boleh dikenali sebagai "port" (pelabuhan)
    assert kueri.kenali_tipe("portal berita") == []


def test_filter_tahun_dan_bendera_asing(kon):
    f, sisa = kueri.kenali_filter(kon, "kapal asing tahun 2024", {"kapal", "pelayaran"})
    jenis = {(x.tipe, x.kolom, x.operator, x.nilai) for x in f}
    assert ("kapal", "bendera", "<>", "Indonesia") in jenis
    assert ("pelayaran", kueri.KOLOM_TAHUN["pelayaran"], "tahun", "2024") in jenis
    # tahun hanya dipasang pada satu tipe (yang paling relevan), bukan semua
    assert sum(x.operator == "tahun" for x in f) == 1


def test_filter_angka_hanya_untuk_tipe_di_jalur(kon):
    f, _ = kueri.kenali_filter(kon, "lebih dari 50.000", {"kapal"})
    assert [(x.tipe, x.kolom, x.operator, float(x.nilai)) for x in f] == [("kapal", "dwt", ">=", 50000.0)]
    f, _ = kueri.kenali_filter(kon, "lebih dari 50.000", {"komoditas"})
    assert f == []
