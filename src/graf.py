"""
graf.py - Mengubah objek + tautan menjadi graf networkx dan gambar Plotly.

Dua kegunaan:
1. `subgraf()` mengambil lingkungan satu objek sampai kedalaman N (ekspansi ala "explore" di Gotham/Foundry).
2. `gambar_graf()` menggambarnya: simpul diwarnai per tipe objek, sisi per tipe tautan, hover berisi properti.
"""

from __future__ import annotations

import sqlite3
from collections import deque

import networkx as nx
import pandas as pd
import plotly.graph_objects as go

from src import basis_data
from src.ontologi import TIPE_OBJEK, TIPE_TAUTAN

BATAS_SIMPUL = 160


def kunci(tipe: str, id_objek: str) -> str:
    return f"{tipe}:{id_objek}"


def pisah(k: str) -> tuple[str, str]:
    tipe, id_objek = k.split(":", 1)
    return tipe, id_objek


def subgraf(kon: sqlite3.Connection, tipe: str, id_objek: str, kedalaman: int = 1,
            tautan_aktif: set[str] | None = None, batas: int = BATAS_SIMPUL,
            tipe_dilewati: set[str] | None = None) -> nx.Graph:
    """BFS dari satu objek lewat tautan ontologi. Simpul membawa atribut tipe, judul, dan properti."""
    g = nx.Graph()
    akar = kunci(tipe, id_objek)
    g.add_node(akar, tipe=tipe, jarak=0)
    antrean = deque([(tipe, id_objek, 0)])
    tipe_dilewati = tipe_dilewati or set()
    while antrean and g.number_of_nodes() < batas:
        t, i, d = antrean.popleft()
        if d >= kedalaman:
            continue
        for l, tujuan, df in basis_data.tetangga(kon, t, i):
            if tautan_aktif is not None and l.id not in tautan_aktif:
                continue
            if tujuan in tipe_dilewati and d + 1 < kedalaman:
                pass
            for _, baris in df.iterrows():
                k = kunci(tujuan, baris["id"])
                baru = k not in g
                if baru:
                    if g.number_of_nodes() >= batas:
                        break
                    g.add_node(k, tipe=tujuan, jarak=d + 1, **{c: baris[c] for c in df.columns})
                    if tujuan not in tipe_dilewati:
                        antrean.append((tujuan, baris["id"], d + 1))
                g.add_edge(kunci(t, i), k, tautan=l.id, label=l.label)
    # lengkapi properti simpul akar
    akar_obj = basis_data.ambil_objek(kon, tipe, id_objek) or {}
    g.nodes[akar].update(akar_obj)
    return g


def judul_simpul(data: dict) -> str:
    t = TIPE_OBJEK[data["tipe"]]
    judul = str(data.get(t.kolom_judul, data.get("id", "")))
    if t.id == "pelayaran":
        judul = f"{data.get('id', '')} {data.get('berangkat', '')}"
    if t.id == "insiden":
        judul = f"{data.get('id', '')}"
    return judul


def _hover(data: dict) -> str:
    t = TIPE_OBJEK[data["tipe"]]
    baris = [f"<b>{t.ikon} {judul_simpul(data)}</b>", f"<i>{t.label}</i>"]
    for p in t.properti:
        if p.nama in data and p.tipe not in ("id", "koordinat") and str(data[p.nama]) not in ("", "nan"):
            nilai = data[p.nama]
            if isinstance(nilai, float) and nilai.is_integer():
                nilai = int(nilai)
            teks = str(nilai)
            if len(teks) > 70:
                teks = teks[:67] + "..."
            baris.append(f"{p.label}: {teks}" + (f" {p.satuan}" if p.satuan else ""))
    return "<br>".join(baris)


def gambar_graf(g: nx.Graph, akar: str | None = None, tinggi: int = 640, seed: int = 7) -> go.Figure:
    """Gambar graf dengan tata letak spring. Satu trace per tipe tautan (sisi) dan per tipe objek (simpul)."""
    if g.number_of_nodes() == 0:
        return go.Figure()
    k = 1.4 / max(1, g.number_of_nodes()) ** 0.5
    pos = nx.spring_layout(g, seed=seed, k=k, iterations=120)
    fig = go.Figure()
    sisi_per_tautan: dict[str, list] = {}
    for a, b, d in g.edges(data=True):
        sisi_per_tautan.setdefault(d["tautan"], []).append((pos[a], pos[b]))
    for tid, daftar in sisi_per_tautan.items():
        xs, ys = [], []
        for (x0, y0), (x1, y1) in daftar:
            xs += [x0, x1, None]
            ys += [y0, y1, None]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(width=1.1, color="#5b6b82"),
                                 name=TIPE_TAUTAN[tid].label, hoverinfo="skip", legendgroup="tautan",
                                 legendgrouptitle_text="Tautan"))
    for tipe, t in TIPE_OBJEK.items():
        simpul = [n for n, d in g.nodes(data=True) if d["tipe"] == tipe]
        if not simpul:
            continue
        ukuran = [26 if n == akar else max(10, 20 - 4 * g.nodes[n].get("jarak", 1)) for n in simpul]
        fig.add_trace(go.Scatter(
            x=[pos[n][0] for n in simpul], y=[pos[n][1] for n in simpul], mode="markers+text",
            text=[judul_simpul(g.nodes[n]) if (n == akar or g.number_of_nodes() <= 45) else "" for n in simpul],
            textposition="top center", textfont=dict(size=10, color="#c3ccd9"),
            marker=dict(size=ukuran, color=t.warna, line=dict(width=[3 if n == akar else 1 for n in simpul],
                                                               color=["#ffffff" if n == akar else "#0b1020" for n in simpul])),
            hovertext=[_hover(g.nodes[n]) for n in simpul], hoverinfo="text",
            customdata=simpul, name=f"{t.ikon} {t.label} ({len(simpul)})", legendgroup="objek",
            legendgrouptitle_text="Objek"))
    fig.update_layout(template="plotly_dark", height=tinggi, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=10, r=10, t=10, b=10), showlegend=True,
                      legend=dict(orientation="v", x=1.0, xanchor="right", y=1.0, bgcolor="rgba(11,16,32,0.6)", font=dict(size=11)),
                      xaxis=dict(visible=False), yaxis=dict(visible=False), hoverlabel=dict(align="left"),
                      font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif"))
    return fig


def ringkasan_graf(g: nx.Graph) -> pd.DataFrame:
    """Jumlah simpul per tipe objek, untuk ditampilkan di samping graf."""
    hitung: dict[str, int] = {}
    for _, d in g.nodes(data=True):
        hitung[d["tipe"]] = hitung.get(d["tipe"], 0) + 1
    return pd.DataFrame([{"tipe": f"{TIPE_OBJEK[t].ikon} {TIPE_OBJEK[t].label}", "jumlah": n}
                         for t, n in sorted(hitung.items(), key=lambda x: -x[1])])


def graf_penuh(kon: sqlite3.Connection, tipe_aktif: set[str]) -> nx.Graph:
    """Graf seluruh ontologi untuk tipe objek terpilih (dipakai untuk statistik derajat)."""
    sisi = basis_data.semua_sisi(kon)
    g = nx.Graph()
    for _, r in sisi.iterrows():
        ts, _ = pisah(r["sumber"])
        tt, _ = pisah(r["tujuan"])
        if ts in tipe_aktif and tt in tipe_aktif:
            g.add_node(r["sumber"], tipe=ts)
            g.add_node(r["tujuan"], tipe=tt)
            g.add_edge(r["sumber"], r["tujuan"], tautan=r["tautan"])
    return g
