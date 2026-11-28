"""
aksi.py - "Action" ala Foundry: perubahan terkendali pada objek, dicatat dalam jejak audit.

Di Foundry, pengguna tidak mengedit tabel secara langsung; mereka menjalankan Action yang sudah
didefinisikan (misalnya "tandai kapal untuk pemeriksaan") dan setiap eksekusi tercatat: siapa, kapan,
objek mana, parameter apa. Di sini jejaknya disimpan di memori sesi (dict yang dikelola app.py), bukan di
basis data, supaya basis data tetap read-only dan setiap pengunjung punya ruang kerja sendiri.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class DefinisiAksi:
    id: str
    label: str
    tipe_objek: tuple[str, ...]        # tipe objek yang bisa menerima aksi ini
    parameter: tuple[tuple[str, str, tuple[str, ...]], ...]   # (nama, label, pilihan; kosong = teks bebas)
    deskripsi: str


DEFINISI_AKSI: dict[str, DefinisiAksi] = {
    "tandai_pemeriksaan": DefinisiAksi(
        "tandai_pemeriksaan", "Tandai untuk pemeriksaan", ("kapal",),
        (("prioritas", "Prioritas", ("rendah", "sedang", "tinggi")), ("alasan", "Alasan", ())),
        "Memasukkan kapal ke daftar pantau pemeriksaan pelabuhan berikutnya."),
    "tambah_catatan": DefinisiAksi(
        "tambah_catatan", "Tambah catatan analis", ("kapal", "perusahaan", "pelabuhan", "komoditas", "provinsi", "pelayaran", "insiden"),
        (("catatan", "Catatan", ()),),
        "Menempelkan catatan bebas pada objek; terlihat di halaman objek selama sesi."),
    "tutup_insiden": DefinisiAksi(
        "tutup_insiden", "Tutup insiden", ("insiden",),
        (("hasil", "Hasil", ("selesai tanpa sanksi", "sanksi administratif", "ditingkatkan ke penyidikan")),),
        "Menandai insiden sebagai ditindaklanjuti dengan hasil tertentu."),
}


@dataclass
class CatatanAudit:
    waktu: datetime
    aksi: str
    tipe: str
    id_objek: str
    judul: str
    parameter: dict = field(default_factory=dict)


def aksi_untuk(tipe: str) -> list[DefinisiAksi]:
    return [a for a in DEFINISI_AKSI.values() if tipe in a.tipe_objek]


def jalankan(audit: list[CatatanAudit], aksi_id: str, tipe: str, id_objek: str, judul: str, parameter: dict | None,
             waktu: datetime | None = None) -> CatatanAudit:
    """Validasi lalu catat eksekusi aksi. Mengembalikan catatan yang baru dibuat."""
    if aksi_id not in DEFINISI_AKSI:
        raise ValueError(f"Aksi '{aksi_id}' tidak dikenal. Pilihan: {', '.join(DEFINISI_AKSI)}")
    a = DEFINISI_AKSI[aksi_id]
    if tipe not in a.tipe_objek:
        raise ValueError(f"Aksi '{a.label}' tidak berlaku untuk tipe {tipe}.")
    if id_objek is None or not str(id_objek).strip():
        # Catatan tanpa objek tidak akan pernah muncul di halaman objek mana pun.
        raise ValueError("Objek tujuan aksi belum dipilih.")
    # Disimpan dalam bentuk rapi supaya riwayat_objek/daftar_pantau tetap menemukannya ("KPL-001 " = "KPL-001").
    id_objek = str(id_objek).strip()
    # Judul kosong/None dulu tercatat apa adanya dan tampil "None" di jejak audit; pakai id-nya.
    judul = str(judul).strip() if judul is not None and str(judul).strip() else id_objek
    parameter = parameter or {}   # tanpa parameter sama sekali: tetap beri pesan "wajib diisi", bukan AttributeError
    bersih: dict = {}
    for nama, label, pilihan in a.parameter:
        nilai = parameter.get(nama)
        nilai = "" if nilai is None else str(nilai).strip()   # None jangan sampai tercatat sebagai teks "None"
        if not nilai:
            raise ValueError(f"Parameter '{label}' wajib diisi.")
        if pilihan:
            # "Tinggi" sama dengan "tinggi"; yang dicatat tetap ejaan resmi dari daftar pilihan.
            cocok = [p for p in pilihan if p.casefold() == nilai.casefold()]
            if not cocok:
                raise ValueError(f"Nilai '{nilai}' tidak termasuk pilihan {label}.")
            nilai = cocok[0]
        bersih[nama] = nilai
    # Yang dicatat adalah nilai yang sudah divalidasi (tanpa spasi tepi), dan hanya parameter milik aksi ini.
    catatan = CatatanAudit(waktu or datetime.now(), aksi_id, tipe, id_objek, judul, bersih)
    audit.append(catatan)
    return catatan


def riwayat_objek(audit: list[CatatanAudit], tipe: str, id_objek: str) -> list[CatatanAudit]:
    # jalankan() menyimpan id tanpa spasi tepi, jadi id yang dicari dirapikan dengan cara yang sama.
    id_objek = "" if id_objek is None else str(id_objek).strip()
    return [c for c in audit if c.tipe == tipe and c.id_objek == id_objek]


def daftar_pantau(audit: list[CatatanAudit]) -> list[CatatanAudit]:
    """Kapal yang ditandai untuk pemeriksaan (catatan terakhir per kapal)."""
    terakhir: dict[str, CatatanAudit] = {}
    for c in audit:
        # "Terakhir" menurut waktu, bukan urutan daftar: catatan bisa ditambahkan dengan waktu lampau.
        if c.aksi == "tandai_pemeriksaan" and (c.id_objek not in terakhir or c.waktu >= terakhir[c.id_objek].waktu):
            terakhir[c.id_objek] = c
    return sorted(terakhir.values(), key=lambda c: c.waktu, reverse=True)
