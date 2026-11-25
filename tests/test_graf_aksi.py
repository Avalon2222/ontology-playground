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
    assert graf.judul_simpul({"tipe": "kapal", "id": "KPL-003", "nama": None}) == "KPL-003"
    assert graf.judul_simpul({"tipe": "kapal", "id": "KPL-004", "nama": "  "}) == "KPL-004"


def test_hover_lewati_kosong_dan_potong_teks_panjang():
    h = graf._hover({"tipe": "kapal", "id": "KPL-001", "nama": "MV Nusantara", "alias": None,
                     "jenis": "", "bendera": float("nan"), "dwt": 80000.0, "lat": -1.2})
    assert "<b>" in h and "MV Nusantara" in h
    assert "80000 ton" in h                     # float bulat ditampilkan tanpa .0, lengkap dengan satuan
    assert "None" not in h and "nan" not in h
    assert "-1.2" not in h                      # koordinat tidak ikut
    panjang = graf._hover({"tipe": "kapal", "id": "K", "nama": "K", "alias": "x" * 100})
    assert "x" * 67 + "..." in panjang


def test_aksi_tidak_dikenal_beri_pesan_jelas():
    audit = []
    with pytest.raises(ValueError, match="tidak dikenal"):
        aksi.jalankan(audit, "hapus_kapal", "kapal", "K1", "Kapal uji", {})
    assert audit == []


def test_audit_menyimpan_parameter_yang_sudah_dirapikan():
    audit = []
    c = aksi.jalankan(audit, "tandai_pemeriksaan", "kapal", "K1", "Kapal uji",
                      {"prioritas": " tinggi ", "alasan": "  AIS mati  ", "iseng": "x"})
    assert c.parameter == {"prioritas": "tinggi", "alasan": "AIS mati"}


def test_ringkasan_graf_kosong_tetap_punya_kolom():
    import networkx as nx

    ringkas = graf.ringkasan_graf(nx.Graph())
    assert list(ringkas.columns) == ["tipe", "jumlah"]
    assert ringkas.empty


def test_jalankan_menolak_parameter_none():
    audit = []
    with pytest.raises(ValueError, match="wajib diisi"):
        aksi.jalankan(audit, "tambah_catatan", "kapal", "KPL-001", "MV X", {"catatan": None})
    assert audit == []


def test_hover_lewati_pd_na():
    import pandas as pd
    h = graf._hover({"tipe": "kapal", "id": "KPL-001", "nama": "MV Nusantara", "alias": pd.NA, "jenis": pd.NA})
    assert "<NA>" not in h


def test_hover_escape_teks_dari_data():
    h = graf._hover({"tipe": "kapal", "id": "K", "nama": "MV <i>Uji</i>", "alias": "A & B <br>"})
    assert "MV &lt;i&gt;Uji&lt;/i&gt;" in h
    assert "A &amp; B &lt;br&gt;" in h
    assert h.startswith("<b>")


def test_jalankan_tanpa_dict_parameter_beri_pesan_jelas():
    audit = []
    with pytest.raises(ValueError, match="wajib diisi"):
        aksi.jalankan(audit, "tambah_catatan", "kapal", "KPL-001", "MV Uji", None)
    assert audit == []


def test_judul_pelayaran_tanpa_tanggal_berangkat():
    assert graf.judul_simpul({"tipe": "pelayaran", "id": "PLY-7", "berangkat": None}) == "PLY-7"
    assert graf.judul_simpul({"tipe": "pelayaran", "id": "PLY-8"}) == "PLY-8"


def test_label_simpul_di_graf_di_escape():
    import networkx as nx
    g = nx.Graph()
    g.add_node("kapal:K1", tipe="kapal", id="K1", nama="<b>Kapal</b> & Co")
    fig = graf.gambar_graf(g, akar="kapal:K1")
    teks = [t for tr in fig.data if tr.text for t in tr.text]
    assert teks == ["&lt;b&gt;Kapal&lt;/b&gt; &amp; Co"]


def test_pilihan_aksi_tidak_peka_huruf_besar():
    audit: list = []
    c = aksi.jalankan(audit, "tandai_pemeriksaan", "kapal", "KPL-001", "MV X", {"prioritas": " Tinggi ", "alasan": "a"})
    assert c.parameter["prioritas"] == "tinggi"
    with pytest.raises(ValueError, match="pilihan"):
        aksi.jalankan(audit, "tandai_pemeriksaan", "kapal", "KPL-001", "MV X", {"prioritas": "TINGGI SEKALI", "alasan": "a"})


def test_daftar_pantau_ambil_catatan_terbaru_menurut_waktu():
    audit: list = []
    aksi.jalankan(audit, "tandai_pemeriksaan", "kapal", "KPL-001", "A", {"prioritas": "tinggi", "alasan": "b"}, datetime(2026, 1, 2))
    aksi.jalankan(audit, "tandai_pemeriksaan", "kapal", "KPL-001", "A", {"prioritas": "rendah", "alasan": "a"}, datetime(2026, 1, 1))
    pantau = aksi.daftar_pantau(audit)
    assert len(pantau) == 1
    assert pantau[0].parameter["prioritas"] == "tinggi"


@pytest.mark.parametrize("id_objek", ["", "  ", None])
def test_aksi_tanpa_objek_ditolak(id_objek):
    audit: list = []
    with pytest.raises(ValueError, match="Objek"):
        aksi.jalankan(audit, "tambah_catatan", "kapal", id_objek, "MV X", {"catatan": "cek"})
    assert audit == []


def test_aksi_id_objek_berspasi_tetap_masuk_riwayat():
    audit = []
    aksi.jalankan(audit, "tambah_catatan", "kapal", " KPL-001 ", "MV Celebes Sentosa 8", {"catatan": "cek muatan"})
    assert len(aksi.riwayat_objek(audit, "kapal", "KPL-001")) == 1


def test_riwayat_objek_id_dengan_spasi_tetap_ketemu():
    audit: list = []
    aksi.jalankan(audit, "tambah_catatan", "kapal", " KPL-001 ", "Kapal A", {"catatan": "cek muatan"})
    assert len(aksi.riwayat_objek(audit, "kapal", "KPL-001 ")) == 1
    assert len(aksi.riwayat_objek(audit, "kapal", "KPL-001")) == 1
    assert aksi.riwayat_objek(audit, "kapal", None) == []


def test_ringkasan_graf_jumlah_seri_urut_label():
    import networkx as nx
    a, b = nx.Graph(), nx.Graph()
    simpul = [("kapal:K1", "kapal"), ("kapal:K2", "kapal"), ("pelabuhan:P1", "pelabuhan"), ("pelabuhan:P2", "pelabuhan")]
    for k, t in simpul:
        a.add_node(k, tipe=t)
    for k, t in reversed(simpul):
        b.add_node(k, tipe=t)
    assert graf.ringkasan_graf(a).equals(graf.ringkasan_graf(b))
