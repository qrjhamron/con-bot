# con-bot

Bot Telegram pribadi untuk **Conflict of Nations: World War 3**, memakai hanya
**Meta Muse Spark 1.3 Contributor**. Beri perintah Bahasa Indonesia, pantau tindakan,
pilih target melalui tombol, dan batalkan tugas dari Telegram.

## Instalasi lokal

Memerlukan Python 3.11 atau lebih baru. Jalankan dari folder proyek:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

Pada Windows, aktifkan virtual environment dengan `.venv\Scripts\Activate.ps1`
dan salin konfigurasi dengan `Copy-Item .env.example .env`.

Isi `.env` dengan `MODEL_API_KEY` dari Meta Model API, `TELEGRAM_BOT_TOKEN` dari
BotFather, `TELEGRAM_OWNER_ID` (ID numerik akun Telegram Anda), `BOT_USER`, dan
`BOT_PASS`. Jangan kirim kredensial melalui chat. Set `GAME_ID` untuk game awal,
atau pilih setelah bot menyala. `PLAYER_ID=0` berarti identitas pemain ditentukan
dari akun di state game; jika identitas tidak tersedia, isi PLAYER_ID untuk GAME_ID
secara eksplisit. Tidak ada negara atau pemain bawaan.

```bash
con-bot
# Alternatif:
python -m sww3bot.telegram_bot
```

Bot menggunakan long polling dan hanya menerima private chat dari pemilik yang
dikonfigurasi. Komputer dan proses harus tetap menyala. Tidak perlu domain atau
webhook. Hanya satu proses Telegram/CLI boleh memakai database yang sama.

## Penggunaan Telegram

| Perintah | Fungsi |
| --- | --- |
| `/start`, `/help` | Bantuan dan game aktif |
| `/games` | Daftar game dengan tombol pilihan |
| `/games ID_GAME` | Buka game tertentu jika daftar akun tidak tersedia |
| `/status` | Ambil dan ringkas status game |
| `/tasks [ID]` | Status tugas, hasil, dan tindakan yang telah dikirim |
| `/cancel [ID]` | Hentikan langkah selanjutnya pada tugas |
| `/reset` | Hapus konteks percakapan game aktif |
| `/auto on`, `/auto off` | Aktifkan/nonaktifkan autoplay eksplisit |

Contoh: `Cek ancaman di sekitar wilayah saya`, `Bangun recruiting office di kota
saya yang belum memilikinya`, atau `Pindahkan pasukan 123 ke provinsi 456`.

Perintah diproses berurutan. Jika nama target ambigu, bot memberikan tombol pilihan.
Pergantian game dan reset ditolak selama tugas masih aktif atau menunggu pilihan.
Pembatalan tidak membatalkan tindakan yang sudah terkirim ke server.

Autoplay menjalankan conquest cycle saat antrean kosong, maksimal satu siklus
bersamaan. Default interval 30 menit; ubah `BOT_AUTO_INTERVAL` jika perlu. Autoplay
nonaktif setelah restart atau pergantian game. `/auto off` menghentikan penjadwalan;
gunakan `/cancel` untuk siklus yang sedang berjalan.

Riwayat per game dan jurnal tugas disimpan dalam `BOT_DB_PATH` (default
`data/con-bot.sqlite3`). Setelah restart, tugas belum selesai ditandai terinterupsi,
dan tindakan dengan hasil yang belum diketahui tidak dikirim ulang. Gunakan
`/status` untuk memeriksa keadaan terbaru. Tugas menunggu pilihan dapat dibuka
kembali melalui `/tasks ID`.

## CLI

CLI memakai mesin agen dan penyimpanan yang sama. Hentikan bot Telegram sebelum
memakai CLI dengan database yang sama.

```bash
con-agent --game 123456 'cek status'
python api/agent.py 'cek status'
python api/agent.py --simple
python api/agent.py --auto --interval 30
```

Skrip aksi lama di `api/` tetap tersedia dengan konteks pemain dinamis. TUI lama
diganti CLI teks. API key model menggunakan `MODEL_API_KEY`; model dan endpoint
dikunci ke `muse-spark-1.3-contributor` dan API Meta, tanpa fallback provider.

## Arsitektur dan batas tugas

- `settings`: konfigurasi tervalidasi dan redaksi kredensial.
- `meta_client`: native tool calling, timeout 60 detik, maksimal tiga percobaan
  untuk jaringan, HTTP 429, dan 5xx.
- `agent_engine`: percakapan, ringkasan riwayat, antrean, dan pembatalan.
- `agent_tools` dan `game_session`: schema argumen, konteks game, pemeriksaan
  kepemilikan, dan jurnal sebelum setiap pengiriman aksi.
- `agent_store`: SQLite untuk sesi, update Telegram, tugas, dan hasil tindakan.
- `telegram_bot` / `agent_cli`: adapter antarmuka.

Default batas satu tugas adalah 15 putaran model dan 30 tool call, serta maksimal
30 pengiriman tindakan game. Ubah `BOT_MAX_ROUNDS` dan `BOT_MAX_TOOLS` di `.env`.
Hasil parsial tetap dicatat jika tugas mencapai batas atau gagal. Teks biasa
berisi JSON tidak dieksekusi sebagai tool.

Tier Contributor mengizinkan Meta menggunakan prompt dan completion untuk
pelatihan. Lihat [model dan tier Meta](https://dev.meta.ai/docs/models) serta
[protokol tool calling](https://dev.meta.ai/docs/tool-calling).

## Pengujian

```bash
python -m pytest tests/ -q
python api/test_agent.py
python api/test_prompts.py
```

Pengujian agen dan Telegram memakai mock; tidak memerlukan token, akses API,
atau menjalankan tindakan game asli. Screenshot, voice, dan pengguna publik
belum didukung.
