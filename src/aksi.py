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


def jalankan(audit: list[CatatanAudit], aksi_id: str, tipe: str, id_objek: str, judul: str, parameter: dict,
             waktu: datetime | None = None) -> CatatanAudit:
    """Validasi lalu catat eksekusi aksi. Mengembalikan catatan yang baru dibuat."""
    a = DEFINISI_AKSI[aksi_id]
    if tipe not in a.tipe_objek:
        raise ValueError(f"Aksi '{a.label}' tidak berlaku untuk tipe {tipe}.")
    for nama, label, pilihan in a.parameter:
        nilai = str(parameter.get(nama, "")).strip()
        if not nilai:
            raise ValueError(f"Parameter '{label}' wajib diisi.")
        if pilihan and nilai not in pilihan:
            raise ValueError(f"Nilai '{nilai}' tidak termasuk pilihan {label}.")
    catatan = CatatanAudit(waktu or datetime.now(), aksi_id, tipe, id_objek, judul, dict(parameter))
    audit.append(catatan)
    return catatan


def riwayat_objek(audit: list[CatatanAudit], tipe: str, id_objek: str) -> list[CatatanAudit]:
    return [c for c in audit if c.tipe == tipe and c.id_objek == id_objek]


def daftar_pantau(audit: list[CatatanAudit]) -> list[CatatanAudit]:
    """Kapal yang ditandai untuk pemeriksaan (catatan terakhir per kapal)."""
    terakhir: dict[str, CatatanAudit] = {}
    for c in audit:
        if c.aksi == "tandai_pemeriksaan":
            terakhir[c.id_objek] = c
    return sorted(terakhir.values(), key=lambda c: c.waktu, reverse=True)
