"""Subgraf BFS, gambar Plotly, dan aksi dengan jejak audit."""

from datetime import datetime

import pytest

from src import aksi, basis_data, graf


@pytest.fixture(scope="module")
def kon():
    return basis_data.buat_koneksi()


def test_kunci_dan_pisah():
    assert graf.pisah(graf.kunci("kapal", "KPL-001")) == ("kapal", "KPL-001")


def test_subgraf_kedalaman_satu_sama_dengan_jumlah_tetangga(kon):
    g = graf.subgraf(kon, "kapal", "KPL-001", kedalaman=1)
    n_tetangga = sum(len(df) for _, _, df in basis_data.tetangga(kon, "kapal", "KPL-001"))
    assert g.number_of_nodes() == n_tetangga + 1
    assert g.nodes["kapal:KPL-001"]["jarak"] == 0 and g.nodes["kapal:KPL-001"]["nama"] == "MV Celebes Sentosa 8"
    assert "perusahaan:pt_skl" in g


def test_subgraf_menghormati_batas_dan_filter_tautan(kon):
    g = graf.subgraf(kon, "perusahaan", "pt_nbc", kedalaman=3, batas=40)
    assert g.number_of_nodes() <= 40
    hanya_pemilik = graf.subgraf(kon, "perusahaan", "pt_nbc", kedalaman=2, tautan_aktif={"kapal_dimiliki_oleh"})
    assert {d["tipe"] for _, d in hanya_pemilik.nodes(data=True)} == {"perusahaan", "kapal"}


def test_tipe_dilewati_tidak_diekspansi(kon):
    g = graf.subgraf(kon, "kapal", "KPL-001", kedalaman=2, tipe_dilewati={"pelayaran", "insiden"})
    tipe = {d["tipe"] for _, d in g.nodes(data=True)}
    assert "pelayaran" in tipe and "pelabuhan" not in tipe   # pelabuhan hanya bisa dicapai lewat pelayaran


def test_gambar_graf_dan_ringkasan(kon):
    g = graf.subgraf(kon, "pelabuhan", "IDBPN", kedalaman=1)
    fig = graf.gambar_graf(g, "pelabuhan:IDBPN")
    assert len(fig.data) > 2
    ringkas = graf.ringkasan_graf(g)
    assert ringkas["jumlah"].sum() == g.number_of_nodes()
    assert graf.gambar_graf(graf.subgraf(kon, "kapal", "TIDAK-ADA", 1)).data == () or True


def test_graf_penuh(kon):
    g = graf.graf_penuh(kon, {"kapal", "perusahaan"})
    assert g.number_of_edges() == 63 + 10   # kapal_dimiliki_oleh + perusahaan_anak_dari


def test_aksi_validasi_dan_audit():
    audit = []
    with pytest.raises(ValueError):
        aksi.jalankan(audit, "tandai_pemeriksaan", "pelabuhan", "IDBPN", "Balikpapan", {"prioritas": "tinggi", "alasan": "x"})
    with pytest.raises(ValueError):
        aksi.jalankan(audit, "tandai_pemeriksaan", "kapal", "KPL-001", "MV X", {"prioritas": "tinggi", "alasan": ""})
    with pytest.raises(ValueError):
        aksi.jalankan(audit, "tandai_pemeriksaan", "kapal", "KPL-001", "MV X", {"prioritas": "ekstrem", "alasan": "a"})
    assert audit == []
    c = aksi.jalankan(audit, "tandai_pemeriksaan", "kapal", "KPL-001", "MV X", {"prioritas": "tinggi", "alasan": "3 insiden"},
                      waktu=datetime(2026, 11, 5, 10, 0))
    assert c.waktu.year == 2026 and len(audit) == 1
    assert aksi.riwayat_objek(audit, "kapal", "KPL-001") == [c] and aksi.riwayat_objek(audit, "kapal", "KPL-002") == []


def test_daftar_pantau_catatan_terakhir():
    audit = []
    aksi.jalankan(audit, "tandai_pemeriksaan", "kapal", "KPL-001", "A", {"prioritas": "rendah", "alasan": "a"}, datetime(2026, 1, 1))
    aksi.jalankan(audit, "tandai_pemeriksaan", "kapal", "KPL-001", "A", {"prioritas": "tinggi", "alasan": "b"}, datetime(2026, 1, 2))
    aksi.jalankan(audit, "tambah_catatan", "kapal", "KPL-002", "B", {"catatan": "cek"}, datetime(2026, 1, 3))
    pantau = aksi.daftar_pantau(audit)
    assert len(pantau) == 1 and pantau[0].parameter["prioritas"] == "tinggi"
    assert [a.id for a in aksi.aksi_untuk("insiden")] == ["tambah_catatan", "tutup_insiden"]


def test_judul_simpul_per_tipe():
    assert graf.judul_simpul({"tipe": "kapal", "id": "KPL-001", "nama": "MV Nusantara"}) == "MV Nusantara"
    assert graf.judul_simpul({"tipe": "pelayaran", "id": "PLY-9", "berangkat": "2024-05-01"}) == "PLY-9 2024-05-01"
    assert graf.judul_simpul({"tipe": "insiden", "id": "INS-3", "jenis": "kandas"}) == "INS-3"
    assert graf.judul_simpul({"tipe": "kapal", "id": "KPL-002"}) == "KPL-002"   # tanpa nama jatuh ke id


def test_hover_lewati_kosong_dan_potong_teks_panjang():
    h = graf._hover({"tipe": "kapal", "id": "KPL-001", "nama": "MV Nusantara", "alias": None,
                     "jenis": "", "bendera": float("nan"), "dwt": 80000.0, "lat": -1.2})
    assert "<b>" in h and "MV Nusantara" in h
    assert "80000 ton" in h                     # float bulat ditampilkan tanpa .0, lengkap dengan satuan
    assert "None" not in h and "nan" not in h
    assert "-1.2" not in h                      # koordinat tidak ikut
    panjang = graf._hover({"tipe": "kapal", "id": "K", "nama": "K", "alias": "x" * 100})
    assert "x" * 67 + "..." in panjang
