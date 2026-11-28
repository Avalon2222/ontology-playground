"""Pemuatan CSV ke SQLite, integritas referensi, akses objek, dan konsol SQL aman."""

import sqlite3

import pytest

from src import basis_data
from src.ontologi import TIPE_OBJEK


@pytest.fixture(scope="module")
def kon():
    return basis_data.buat_koneksi()


def test_jumlah_objek_sesuai_csv(kon):
    jumlah = basis_data.hitung_objek(kon)
    for t in TIPE_OBJEK:
        assert jumlah[t] == len(basis_data.muat_tabel(t)) > 0


def test_integritas_referensi_bersih(kon):
    assert basis_data.cek_integritas(kon) == []


def test_id_unik(kon):
    for t in TIPE_OBJEK:
        n, n_unik = kon.execute(f"SELECT COUNT(*), COUNT(DISTINCT id) FROM {t}").fetchone()
        assert n == n_unik


def test_kode_hs_tetap_teks(kon):
    # '09' (kopi) tidak boleh berubah menjadi 9
    assert kon.execute("SELECT hs_bab FROM komoditas WHERE id = 'kopi'").fetchone()[0] == "09"


def test_ambil_dan_judul(kon):
    o = basis_data.ambil_objek(kon, "pelabuhan", "IDBPN")
    assert o["nama"] == "Balikpapan" and o["provinsi_id"] == "ID-KI"
    assert basis_data.ambil_objek(kon, "pelabuhan", "XXXXX") is None
    assert basis_data.judul_objek(kon, "provinsi", "ID-KI") == "Kalimantan Timur"
    assert basis_data.judul_objek(kon, "pelayaran", "VOY-0001").startswith("VOY-0001 ·")


def test_cari_objek_nama_alias_dan_filter(kon):
    assert basis_data.cari_objek(kon, "provinsi", "kaltim")["id"].tolist() == ["ID-KI"]
    assert "IDJKT" in basis_data.cari_objek(kon, "pelabuhan", "priok")["id"].tolist()
    tanker = basis_data.cari_objek(kon, "kapal", "", {"jenis": ["tanker"]})
    assert len(tanker) > 0 and (tanker["jenis"] == "tanker").all()
    assert basis_data.cari_objek(kon, "kapal", "tidak-ada-kapal-ini").empty


def test_tetangga_kapal_memuat_pemilik_dan_pelayaran(kon):
    hasil = {l.label: (tujuan, df) for l, tujuan, df in basis_data.tetangga(kon, "kapal", "KPL-001")}
    assert hasil["dimiliki oleh"][0] == "perusahaan" and hasil["dimiliki oleh"][1].iloc[0]["id"] == "pt_skl"
    assert hasil["melakukan pelayaran"][0] == "pelayaran" and len(hasil["melakukan pelayaran"][1]) > 0


def test_tetangga_tautan_diri_sendiri_dua_arah(kon):
    hasil = {l.label: df for l, _, df in basis_data.tetangga(kon, "perusahaan", "grp_khatulistiwa")}
    assert set(hasil["induk dari"]["id"]) == {"pt_skl", "pt_bauksit"}
    assert hasil["anak usaha dari"].empty
    anak = {l.label: df for l, _, df in basis_data.tetangga(kon, "perusahaan", "pt_skl")}
    assert anak["anak usaha dari"]["id"].tolist() == ["grp_khatulistiwa"]


def test_semua_sisi_jumlahnya_sama_dengan_hitung_tautan(kon):
    assert len(basis_data.semua_sisi(kon)) == sum(basis_data.hitung_tautan(kon).values())


@pytest.mark.parametrize("sql", [
    "DELETE FROM kapal", "SELECT 1; DROP TABLE kapal", "PRAGMA table_info(kapal)", "", "UPDATE kapal SET dwt = 0",
    "WITH x AS (SELECT 1) INSERT INTO kapal VALUES (1)",
])
def test_sql_aman_menolak(kon, sql):
    with pytest.raises(basis_data.KesalahanSQL):
        basis_data.jalankan_sql_aman(kon, sql)


def test_sql_aman_menjalankan_select_dan_membatasi(kon):
    df = basis_data.jalankan_sql_aman(kon, "select * from pelayaran", batas=10)
    assert len(df) == 10
    df = basis_data.jalankan_sql_aman(kon, "WITH k AS (SELECT * FROM kapal) SELECT COUNT(*) AS n FROM k;")
    assert int(df.iloc[0]["n"]) == 63


def test_koneksi_read_only(kon):
    with pytest.raises(sqlite3.OperationalError):
        kon.execute("DELETE FROM kapal")
    assert kon.execute("SELECT COUNT(*) FROM kapal").fetchone()[0] == 63


@pytest.mark.parametrize("tipe", list(TIPE_OBJEK))
def test_semua_objek_terurut_menurut_judul(kon, tipe):
    df = basis_data.semua_objek(kon, tipe)
    assert not df.empty
    judul = df[TIPE_OBJEK[tipe].kolom_judul].tolist()
    assert judul == sorted(judul)


def test_sql_df_pakai_parameter(kon):
    df = basis_data.sql_df(kon, "SELECT COUNT(*) AS n FROM kapal WHERE id = ?", ("tidak-ada",))
    assert df.iloc[0]["n"] == 0


def test_sql_tetangga_dua_arah(kon):
    from src import ontologi
    for l in ontologi.TIPE_TAUTAN.values():
        if l.sumber == l.tujuan:
            continue
        for dari in (l.sumber, l.tujuan):
            sql = basis_data.sql_tetangga(l, dari)
            assert sql.startswith(f"SELECT t.* FROM {l.ujung_lain(dari)} t JOIN {l.tabel} r")
            # SQL-nya harus valid untuk SQLite walau id-nya tidak ada.
            assert basis_data.sql_df(kon, sql, ("tidak-ada",)).empty


def test_cari_objek_wildcard_dicari_apa_adanya(kon):
    assert basis_data.cari_objek(kon, "kapal", "%").empty
    assert basis_data.cari_objek(kon, "kapal", "_").empty
    contoh = basis_data.semua_objek(kon, "kapal")["id"].iloc[0]
    assert contoh in basis_data.cari_objek(kon, "kapal", contoh)["id"].tolist()


def test_cari_objek_spasi_tepi_diabaikan(kon):
    semua = basis_data.cari_objek(kon, "kapal")
    assert len(basis_data.cari_objek(kon, "kapal", "   ")) == len(semua)
    nama = semua["nama"].iloc[0]
    assert nama in basis_data.cari_objek(kon, "kapal", f"  {nama} ")["nama"].tolist()
    assert len(basis_data.cari_objek(kon, "kapal", None)) == len(semua)


@pytest.mark.parametrize("kosong", [None, float("nan"), "  "])
def test_judul_objek_judul_kosong_pakai_id(monkeypatch, kosong):
    monkeypatch.setattr(basis_data, "ambil_objek", lambda kon, tipe, i: {"id": "KPL-X", "nama": kosong})
    assert basis_data.judul_objek(None, "kapal", "KPL-X") == "KPL-X"


@pytest.mark.parametrize("tipe,kolom", [("pelayaran", "berangkat"), ("insiden", "jenis")])
@pytest.mark.parametrize("kosong", [None, float("nan"), ""])
def test_judul_objek_keterangan_kosong_cukup_id(monkeypatch, tipe, kolom, kosong):
    monkeypatch.setattr(basis_data, "ambil_objek", lambda kon, t, i: {"id": "X-1", kolom: kosong})
    assert basis_data.judul_objek(None, tipe, "X-1") == "X-1"


@pytest.mark.parametrize("batas", [0, -1, -50])
def test_sql_aman_batas_negatif_tidak_jadi_tanpa_batas(kon, batas):
    hasil = basis_data.jalankan_sql_aman(kon, "SELECT * FROM kapal", batas=batas)
    assert len(hasil) == 1


def test_cari_objek_batas_negatif_tidak_mengembalikan_semua(kon):
    assert basis_data.cari_objek(kon, "kapal", batas=-1).empty
    assert len(basis_data.cari_objek(kon, "kapal", batas=2)) == 2


def test_cari_objek_filter_satu_teks_tidak_dipecah_per_huruf(kon):
    daftar = basis_data.cari_objek(kon, "kapal", "", {"jenis": ["tanker"]})
    satu = basis_data.cari_objek(kon, "kapal", "", {"jenis": "tanker"})
    assert len(daftar) > 0
    assert satu["id"].tolist() == daftar["id"].tolist()


def test_muat_tabel_angka_tak_hingga_jadi_kosong(tmp_path):
    (tmp_path / "kapal.csv").write_text(
        "id,nama,dwt,panjang_m,tahun_dibangun\nK1,A,inf,120,2010\nK2,B,5000,-inf,2012\n", encoding="utf-8"
    )
    df = basis_data.muat_tabel("kapal", tmp_path)
    assert df["dwt"].isna().tolist() == [True, False]
    assert df["panjang_m"].isna().tolist() == [False, True]
    assert df["id"].tolist() == ["K1", "K2"]


def test_sql_aman_kata_terlarang_di_dalam_teks_boleh(kon):
    df = basis_data.jalankan_sql_aman(kon, "SELECT 'drop; delete' AS catatan, COUNT(*) AS n FROM kapal WHERE nama <> 'it''s update'")
    assert df.loc[0, "catatan"] == "drop; delete"
    assert df.loc[0, "n"] > 0
    with pytest.raises(basis_data.KesalahanSQL):
        basis_data.jalankan_sql_aman(kon, "SELECT 'x'; DROP TABLE kapal")


def test_sql_aman_fungsi_replace_boleh(kon):
    df = basis_data.jalankan_sql_aman(kon, "SELECT REPLACE(nama, 'PT ', '') AS singkat FROM perusahaan", batas=3)
    assert len(df) == 3
    assert not df["singkat"].str.startswith("PT ").any()
    with pytest.raises(basis_data.KesalahanSQL):
        basis_data.jalankan_sql_aman(kon, "WITH x AS (SELECT 1) REPLACE INTO kapal VALUES (1)")


def test_muat_tabel_spasi_di_teks_dibuang(tmp_path):
    (tmp_path / "kapal.csv").write_text(
        "id,nama,bendera,dwt,pemilik_id\nK1 ,A, Indonesia,100, pt_a\n", encoding="utf-8"
    )
    df = basis_data.muat_tabel("kapal", tmp_path)
    assert df.loc[0, ["id", "nama", "bendera", "pemilik_id"]].tolist() == ["K1", "A", "Indonesia", "pt_a"]
    assert df.loc[0, "dwt"] == 100


def test_cari_objek_spasi_ganda_di_tengah_diabaikan(kon):
    semua = basis_data.cari_objek(kon, "kapal")
    nama = next(n for n in semua["nama"] if " " in n)
    dobel = nama.replace(" ", "  ", 1)
    assert nama in basis_data.cari_objek(kon, "kapal", dobel)["nama"].tolist()
    assert nama in basis_data.cari_objek(kon, "kapal", nama.replace(" ", "\t", 1))["nama"].tolist()


def test_sql_aman_komentar_di_akhir_kueri(kon):
    df = basis_data.jalankan_sql_aman(kon, "SELECT COUNT(*) AS n FROM kapal -- jumlah semua kapal", batas=5)
    assert df["n"].iloc[0] == basis_data.hitung_objek(kon)["kapal"]
    df = basis_data.jalankan_sql_aman(kon, "SELECT id FROM kapal -- tanpa titik koma", batas=3)
    assert len(df) == 3


def test_cari_objek_nilai_filter_berspasi(kon):
    biasa = basis_data.cari_objek(kon, "kapal", "", {"jenis": ["tanker"]})
    assert basis_data.cari_objek(kon, "kapal", "", {"jenis": [" tanker "]})["id"].tolist() == biasa["id"].tolist()
    assert len(basis_data.cari_objek(kon, "kapal", "", {"jenis": "tanker  "})) == len(biasa)


def test_ambil_objek_dan_tetangga_id_berspasi(kon):
    kapal = basis_data.semua_objek(kon, "kapal")["id"].iloc[0]
    assert basis_data.ambil_objek(kon, "kapal", f" {kapal} ")["id"] == kapal
    biasa = [(l.id, len(df)) for l, _, df in basis_data.tetangga(kon, "kapal", kapal)]
    assert [(l.id, len(df)) for l, _, df in basis_data.tetangga(kon, "kapal", f"{kapal}  ")] == biasa
    assert sum(n for _, n in biasa) > 0


def test_muat_tabel_desimal_koma_tetap_terbaca(tmp_path):
    (tmp_path / "kapal.csv").write_text(
        'id,nama,dwt,panjang_m\nK1,A,"14000,5","62,3"\nK2,B,5000,120\nK3,C,"1,2,3",80\n', encoding="utf-8"
    )
    df = basis_data.muat_tabel("kapal", tmp_path)
    assert df["dwt"].tolist()[:2] == [14000.5, 5000.0]
    assert df["panjang_m"].tolist()[:2] == [62.3, 120.0]
    assert df["dwt"].isna().tolist() == [False, False, True]


def test_muat_tabel_id_ganda_pakai_baris_pertama(tmp_path):
    (tmp_path / "kapal.csv").write_text(
        "id,nama,dwt\nK1,A,100\nK2,B,200\nK1 ,A (salinan),300\n", encoding="utf-8"
    )
    df = basis_data.muat_tabel("kapal", tmp_path)
    assert df["id"].tolist() == ["K1", "K2"]
    assert df["nama"].tolist() == ["A", "B"]


def test_cari_objek_nilai_filter_tidak_peka_huruf(kon):
    biasa = basis_data.cari_objek(kon, "kapal", "", {"jenis": ["kapal kontainer"]})
    assert len(biasa) > 0
    assert basis_data.cari_objek(kon, "kapal", "", {"jenis": ["Kapal Kontainer"]})["id"].tolist() == biasa["id"].tolist()
    assert basis_data.cari_objek(kon, "kapal", "", {"jenis": "KAPAL KONTAINER"})["id"].tolist() == biasa["id"].tolist()
