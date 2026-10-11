# con-bot

Bot Telegram pribadi untuk **Conflict of Nations: World War 3**, memakai hanya
**Meta Muse Spark 1.3 Contributor**. Tanya atau beri perintah Bahasa Indonesia, pantau tindakan,
pilih target melalui tombol, dan batalkan tugas dari Telegram.

## Instalasi lokal

Kontrol ekonomi selama tidur: `/overnight 8` menjalankan cek setiap 10 menit selama
maksimal 8 jam. Bot memprioritaskan Arms Industry di kota sendiri yang belum punya,
menunggu slot kosong dan biaya yang dapat dibayar, serta menjaga cadangan resource.
Setiap cek mengirim maksimal satu upgrade melalui executor dengan verifikasi state.
`/overnight status` melihat hasil terakhir; `/overnight off` atau `/cancel` menghentikan
kontrol. Batas waktu tetap berlaku setelah restart. Mode berhenti jika aksi ditolak
atau hasilnya belum jelas; Goldmark, diplomasi, dan perintah pasukan tidak termasuk
dalam kontrol ekonomi ini. Proses bot harus tetap menyala.

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

Langsung kirim chat biasa, misalnya `Negara gua aman nggak?`, `Bagusnya gua bangun
apa dulu?`, atau `Kenapa resource gua kurang?`. Pertanyaan lanjutan seperti `kenapa?`
memakai konteks percakapan game aktif. Bot diarahkan untuk menjawab pertanyaan dan
saran dengan analisis; tindakan hanya dilakukan atas permintaan yang jelas.

`/start` menampilkan tombol **Kondisi negara**, **Saran langkah**, **Pasukan**, dan
**Ekonomi**. Jawaban chat ditampilkan langsung tanpa nomor tugas dan nama tool.
Jurnal tetap tersedia melalui `/tasks` untuk memeriksa tindakan atau kegagalan.

Versi 2.0.3 menambahkan antrean bangunan tetap: minta "bangun A, B, C",
bot mengantrekan tiap bangunan dan mengerjakannya berurutan lewat pengiriman
terverifikasi; antrean lanjut setelah restart. Verifikasi konstruksi kini
membedakan selesai (`us`) vs masih dibangun (`cos`), dan pembatalan slot
dikonfirmasi dari slot yang terbaca kosong.

Versi 2.0.2 menambahkan pembacaan snapshot intel militer hari berjalan dari laporan
spy resmi game. Tanyakan, misalnya, “ada intel pasukan Niger?”; laporan dapat difilter
dengan ID kota, dan bot menyebutkan hari/sumber snapshot. Data hari sebelumnya tidak
disajikan sebagai kondisi saat ini. Bot hanya menampilkan komposisi yang disediakan
oleh laporan intel game.

Versi 2.0.1 memakai katalog resmi untuk nama unit/bangunan dan membaca aktivitas
pasukan dari antrean perintah serta fight status. Respons server diterima belum
berarti aksi berhasil: bot memeriksa perubahan state, menghentikan hasil yang
belum terverifikasi, dan tidak mengirim ulang perintah yang sama. Rute manual
yang sudah ada dilaporkan sebagai kondisi yang sudah berlaku.
Rincian sumber dan mapping ada di [audit protokol](docs/protocol-mapping.md).

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


## Commander 2.1

- `/commander 8`: aktifkan ekonomi, produksi infanteri, riset relevan, dan pertahanan
  selama maksimal delapan jam. `/commander status` dan `/commander off` untuk kontrol.
- `/queue`, `/queue pause`, `/queue resume`: antrean persisten untuk bangunan,
  produksi, riset, dan perpindahan. Dependency menunggu bukti penyelesaian dari game.
  Perintah diterima belum berarti selesai; hasil belum jelas tidak dikirim ulang.
- `/economy`: budget rencana, cadangan, biaya pemeliharaan, dan perkiraan kekurangan.
  Budget dan ketersediaan slot diperiksa lagi sebelum pengiriman.
- `/military`: unit sendiri yang idle dan kota tanpa garnisun. Penempatan otomatis
  hanya menuju wilayah sendiri, memakai unit darat, menjaga garnisun dan morale.
- `/events`: perubahan kepemilikan, pekerjaan selesai, riset, unit, perang, dan
  resource. Perubahan penting mengirim pemberitahuan; planner memperbarui rencana
  setiap lima menit dari state terbaru. Intel musuh hanya memakai laporan sah.

Antrean manual tetap dapat diproses di luar periode otomatis. Antrean otomatis
berhenti saat periode berakhir; pekerjaan yang sudah diterima tetap dipantau.
Tidak ada perpanjangan otomatis, pembelian Gold, atau pembacaan unit musuh tersembunyi.


## Rute dan conquest 2.2

Bot memahami perintah biasa, misalnya:

- “Gerakkan pasukan 123 ke provinsi 10, lalu 20, lalu 30.”
- “Pasukan 123 ke 10 lalu 20, pasukan 456 ke 30 lalu 40.”
- “Taklukkan semua homeland negara X pakai pasukan cadangan.”
- “Tunjukkan homeland dan kota negara X.” atau `/map X`.
- “Musuh yang terlihat sekarang di mana?” atau `/contacts`.

`get_campaign_plan` membuat preview; `queue_campaign` menyimpan maksimal 200
tujuan dalam satu transaksi. Rute tiap pasukan berurutan dan beberapa pasukan
bisa bergerak bersamaan. Perintah yang sudah berjalan tidak ditimpa. Garnisun
kota dipertahankan secara default; override hanya jika diminta pengguna.
`cancel_campaign` membatalkan tujuan yang belum dikirim, sedangkan `/queue pause`
menghentikan pengiriman baru.

Homeland memakai `ci`/coreIDs dari game; kota memakai `plv >= 4`. Pemilik sekarang
dan pemilik core dipisahkan, termasuk homeland yang telah diduduki negara lain.
Conquer hanya selesai ketika kepemilikan berubah. Target yang belum dalam perang
menunggu diplomasi; campaign tidak otomatis mendeklarasikan perang. Planner
pertahanan otomatis tidak mengambil pasukan yang telah diberi rute manual.

Intel tanpa spy memakai kontak dalam sight pasukan darat sendiri, kontak tempur,
atau akses militer resmi. Filter sight memakai setengah `vw`/`dvw`, sesuai diameter
area pandang pada client resmi. Unit stealth, kontak tersamar, posisi pesawat yang
belum bisa diinterpolasi, dan area di luar pandangan tidak dianggap diketahui.
Riwayat `last_seen` disimpan terpisah dan bukan posisi saat ini. Jumlah seluruh
musuh atau kota kosong tidak dapat dipastikan dari ketiadaan kontak.


## Combat planner dan koordinasi 2.3

- `/combat target`: analisis HP, komposisi dan peran unit, terrain, damage terhadap
  kontak musuh yang benar-benar terlihat, serta alasan maju atau menahan serangan.
- “Kumpulkan pasukan A, B, C di wilayah X, lalu serang Y bersama”: preview memakai
  `get_coordination_plan`; perintah nyata memakai `queue_campaign coordinate=true`.
- `/coordination`: status rally, target berikutnya, dan alasan kelompok tertahan.
- `combat_policy` mengatur batas kesehatan (default 55%), margin damage (default
  1,5; target kota minimal 2), dan `hold_unknown` untuk meminta intel sebelum maju.

Conquer diperiksa lagi sebelum dikirim: HP rendah, kontak yang belum teridentifikasi,
stat/terrain yang tidak diketahui, stacking besar yang belum dimodelkan, atau
estimasi yang kurang kuat membuat queue menunggu. Tanpa kontak, default masih
mengizinkan pendekatan berhati-hati pada perintah conquer yang telah diberikan;
`hold_unknown=true` menahan pendekatan itu. Ketiadaan kontak bukan bukti wilayah kosong.

Koordinasi menyimpan satu node rally dan rute kelompok berurutan. Semua anggota
harus tiba dan idle dahulu; default `require_merged=true` menunggu satu stack agar
pasukan maju dengan kecepatan kelompok. Override hanya ketika pengguna menerima
waktu tiba terpisah. Perintah maju dikirim dalam satu `UltArmyAction`; ini
menyamakan waktu pemberian perintah, bukan waktu tiba. Unit penakluk dan artileri
pendukung boleh bergabung. Rally harus wilayah sendiri dan tidak mengandung unit
di luar kelompok. Garnisun kota awal dipertahankan sesuai opsi campaign.

Keanggotaan memakai ID unit sendiri sehingga merge yang mempertahankan ID unit
dapat diikuti. ID unit hilang/berubah atau merge dengan unit di luar rencana
menahan kelompok untuk penilaian ulang. Status `accepted` tetap belum berarti
tiba atau conquer selesai. `/queue pause` dan `cancel_campaign` tetap berlaku.

Estimasi memakai pemetaan client resmi: terrain `tt`, `strength`/`defence`,
`unitFeatures` sebagai faktor damage, `damageTypes`, dan `sizeFactors`. HP mentah
per entry sudah mencakup jumlah unit, sehingga tidak dikalikan dua kali. Buff,
fortifikasi, mobilisasi, dan stacking belum dihitung lengkap. Planner memberi
estimasi terbatas untuk tempur darat; tidak melaporkan probabilitas kemenangan.

Audit `exploits.py`: keterangan historis disesuaikan dengan perilaku server,
orders sendiri dibaca dari `c`, jumlah unit dan HP dipisahkan, dan laporan pasukan
asing melewati filter visibility. Spy dan premium tetap mengikuti biaya game;
combat planner dan koordinasi tidak membelanjakan Goldmark.

### Nama kota dan waktu (2.3.1)

Bot mengambil nama wilayah dari endpoint peta lengkap resmi dan menyimpannya
per peta untuk laporan serta pencarian kota. ID tetap dipakai untuk perintah
internal; nama yang belum tersedia ditandai tanpa menebak kota. Durasi produksi,
konstruksi, riset, dan pergantian hari memakai timestamp server serta timeScale
untuk menghitung jam nyata. ETA nol tidak dianggap bukti pekerjaan selesai.

### Planner lanjut dan full auto (2.4.0)

- `/stacks`: optimizer grup army sendiri memakai penalti stack dari mod game aktif,
  HP, terrain, peran unit dan proxy kerentanan echelon. Tidak memecah unit otomatis;
  buff officer/token dan casualty echelon belum dihitung sebagai simulasi server.
- `/air`: pangkalan operasional, jangkauan pertahanan, flight budget dan refuel
  dalam waktu nyata. Queue mendukung `air_patrol` dan `air_relocate` dengan command
  udara resmi dan verifikasi state; `naval_move` untuk posisi penjagaan laut.
- `/occupation`: risiko insurgency, garnisun yang benar-benar tiba, reinforcement
  dan kelayakan pelepasan. Garnisun terakhir dipertahankan. Waktu revolt tidak ditebak.
- `simulate_strategy_options`: bandingkan hingga enam pilihan pasukan dan target.
  Perbandingan memakai keadaan sekarang, tidak menjanjikan peluang menang atau
  keadaan musuh di masa depan. Bisa diminta lewat chat tanpa command khusus.
- `research_strategy`: membaca wiki resmi di internet, menyertakan sumber dan
  waktu pengambilan, cache 15 menit. `search_web` mencari panduan tambahan dan
  membedakan hasil pencarian dari artikel yang benar-benar dibaca.

`/fullauto` atau chat “aktifkan full auto” mengaktifkan sesi 8 jam;
`/fullauto 4` memilih 4 jam, `/fullauto status` membaca keadaan,
`/fullauto off` menghentikan sesi. Deadline tersimpan dan tetap sama setelah restart.
Model Muse Spark menggunakan `reasoning_effort=high`. Evaluasi 5 menit mencakup
seluruh army, resource, kota, kontak sah, occupation, pangkalan, produksi dan riset.
Model memilih paling banyak enam opsi yang divalidasi; executor membaca ulang state
sebelum mengirim dan queue menunggu penyelesaian aktual. Penaklukan otomatis memilih
perang yang sudah aktif dengan intel dan margin memadai. Fog tetap unknown.

Bot mengirim laporan tindakan/perubahan penting dan ringkasan setiap 30 menit.
Keputusan menahan unit karena garnisun, HP, resource atau refuel juga dicatat.
Panduan internet diperlakukan sebagai data; config game lebih utama daripada wiki
yang lama. Mode ini membutuhkan proses bot tetap hidup dan koneksi API tersedia.
