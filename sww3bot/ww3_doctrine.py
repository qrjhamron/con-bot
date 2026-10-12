"""Doktrin WW3 4x per negara, hasil riset game live.
Sumber: start day-1 game 10928419 + akhir day-13 game 10925912.
Diregenerasi manual bila meta berubah; angka = observasi, bukan resep mutlak.
"""
SOURCE = {"start_game": 10928419, "start_day": 1, "end_game": 10925912, "end_day": 13}

NATIONS = {
  "Algeria": {
    "pid": 1,
    "archetype": "major",
    "start_provinces": 47,
    "start_income": 6578,
    "start_vp": 70,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "DR Congo": {
    "pid": 2,
    "archetype": "major",
    "start_provinces": 49,
    "start_income": 5685,
    "start_vp": 70,
    "day13_vp": 343,
    "day13_provinces": 228,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 343 VP / 228 provinsi."
  },
  "Egypt": {
    "pid": 3,
    "archetype": "major",
    "start_provinces": 49,
    "start_income": 6969,
    "start_vp": 75,
    "day13_vp": 256,
    "day13_provinces": 153,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 256 VP / 153 provinsi."
  },
  "South Africa": {
    "pid": 4,
    "archetype": "major",
    "start_provinces": 46,
    "start_income": 5755,
    "start_vp": 67,
    "day13_vp": 85,
    "day13_provinces": 50,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 85 VP / 50 provinsi."
  },
  "China": {
    "pid": 5,
    "archetype": "superpower",
    "start_provinces": 66,
    "start_income": 9774,
    "start_vp": 103,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Ekspansi 2-3 front sekaligus ke AI tetangga",
      "Arms Industry kedua setelah ekonomi jalan"
    ],
    "priorities": [
      "morale lintas front",
      "produksi udara/laut untuk proyeksi",
      "VP race"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "India": {
    "pid": 6,
    "archetype": "major",
    "start_provinces": 58,
    "start_income": 9329,
    "start_vp": 92,
    "day13_vp": 320,
    "day13_provinces": 183,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 320 VP / 183 provinsi."
  },
  "Indonesia": {
    "pid": 7,
    "archetype": "major",
    "start_provinces": 53,
    "start_income": 6761,
    "start_vp": 77,
    "day13_vp": 239,
    "day13_provinces": 146,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 239 VP / 146 provinsi."
  },
  "Iran": {
    "pid": 8,
    "archetype": "major",
    "start_provinces": 49,
    "start_income": 7470,
    "start_vp": 76,
    "day13_vp": 118,
    "day13_provinces": 73,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 118 VP / 73 provinsi."
  },
  "Japan": {
    "pid": 9,
    "archetype": "major",
    "start_provinces": 49,
    "start_income": 6449,
    "start_vp": 72,
    "day13_vp": 48,
    "day13_provinces": 30,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 48 VP / 30 provinsi."
  },
  "Saudi Arabia": {
    "pid": 10,
    "archetype": "major",
    "start_provinces": 44,
    "start_income": 6306,
    "start_vp": 67,
    "day13_vp": 112,
    "day13_provinces": 63,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 112 VP / 63 provinsi."
  },
  "Thailand": {
    "pid": 11,
    "archetype": "major",
    "start_provinces": 46,
    "start_income": 6561,
    "start_vp": 69,
    "day13_vp": 209,
    "day13_provinces": 110,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 209 VP / 110 provinsi."
  },
  "Turkey": {
    "pid": 12,
    "archetype": "major",
    "start_provinces": 52,
    "start_income": 6475,
    "start_vp": 76,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "France": {
    "pid": 13,
    "archetype": "major",
    "start_provinces": 45,
    "start_income": 7487,
    "start_vp": 71,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Germany": {
    "pid": 14,
    "archetype": "major",
    "start_provinces": 44,
    "start_income": 7708,
    "start_vp": 71,
    "day13_vp": 241,
    "day13_provinces": 139,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 241 VP / 139 provinsi."
  },
  "Italy": {
    "pid": 15,
    "archetype": "major",
    "start_provinces": 48,
    "start_income": 6139,
    "start_vp": 69,
    "day13_vp": 27,
    "day13_provinces": 21,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 27 VP / 21 provinsi."
  },
  "Poland": {
    "pid": 16,
    "archetype": "major",
    "start_provinces": 56,
    "start_income": 6977,
    "start_vp": 80,
    "day13_vp": 275,
    "day13_provinces": 176,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 275 VP / 176 provinsi."
  },
  "Russia": {
    "pid": 17,
    "archetype": "superpower",
    "start_provinces": 82,
    "start_income": 9720,
    "start_vp": 118,
    "day13_vp": 119,
    "day13_provinces": 73,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Ekspansi 2-3 front sekaligus ke AI tetangga",
      "Arms Industry kedua setelah ekonomi jalan"
    ],
    "priorities": [
      "morale lintas front",
      "produksi udara/laut untuk proyeksi",
      "VP race"
    ],
    "benchmark": "Tertinggi teramati day-13: 119 VP / 73 provinsi."
  },
  "Sweden": {
    "pid": 18,
    "archetype": "major",
    "start_provinces": 50,
    "start_income": 6596,
    "start_vp": 74,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "United Kingdom": {
    "pid": 19,
    "archetype": "major",
    "start_provinces": 48,
    "start_income": 6575,
    "start_vp": 71,
    "day13_vp": 292,
    "day13_provinces": 173,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 292 VP / 173 provinsi."
  },
  "Canada": {
    "pid": 20,
    "archetype": "superpower",
    "start_provinces": 63,
    "start_income": 6766,
    "start_vp": 88,
    "day13_vp": 7,
    "day13_provinces": 7,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Ekspansi 2-3 front sekaligus ke AI tetangga",
      "Arms Industry kedua setelah ekonomi jalan"
    ],
    "priorities": [
      "morale lintas front",
      "produksi udara/laut untuk proyeksi",
      "VP race"
    ],
    "benchmark": "Tertinggi teramati day-13: 7 VP / 7 provinsi."
  },
  "Mexico": {
    "pid": 21,
    "archetype": "major",
    "start_provinces": 53,
    "start_income": 5210,
    "start_vp": 73,
    "day13_vp": 89,
    "day13_provinces": 55,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 89 VP / 55 provinsi."
  },
  "United States": {
    "pid": 22,
    "archetype": "superpower",
    "start_provinces": 82,
    "start_income": 9855,
    "start_vp": 118,
    "day13_vp": 225,
    "day13_provinces": 139,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Ekspansi 2-3 front sekaligus ke AI tetangga",
      "Arms Industry kedua setelah ekonomi jalan"
    ],
    "priorities": [
      "morale lintas front",
      "produksi udara/laut untuk proyeksi",
      "VP race"
    ],
    "benchmark": "Tertinggi teramati day-13: 225 VP / 139 provinsi."
  },
  "Argentina": {
    "pid": 23,
    "archetype": "major",
    "start_provinces": 49,
    "start_income": 6614,
    "start_vp": 73,
    "day13_vp": 3,
    "day13_provinces": 3,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 3 VP / 3 provinsi."
  },
  "Brazil": {
    "pid": 24,
    "archetype": "major",
    "start_provinces": 56,
    "start_income": 8460,
    "start_vp": 88,
    "day13_vp": 158,
    "day13_provinces": 78,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 158 VP / 78 provinsi."
  },
  "Colombia": {
    "pid": 25,
    "archetype": "major",
    "start_provinces": 47,
    "start_income": 6219,
    "start_vp": 68,
    "day13_vp": 142,
    "day13_provinces": 87,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 142 VP / 87 provinsi."
  },
  "Australia": {
    "pid": 26,
    "archetype": "major",
    "start_provinces": 54,
    "start_income": 6395,
    "start_vp": 77,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Cameroon": {
    "pid": 27,
    "archetype": "major",
    "start_provinces": 46,
    "start_income": 5594,
    "start_vp": 67,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Chad": {
    "pid": 28,
    "archetype": "major",
    "start_provinces": 49,
    "start_income": 6379,
    "start_vp": 72,
    "day13_vp": 260,
    "day13_provinces": 171,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 260 VP / 171 provinsi."
  },
  "Ghana": {
    "pid": 29,
    "archetype": "minor",
    "start_provinces": 13,
    "start_income": 546,
    "start_vp": 16,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Libya": {
    "pid": 30,
    "archetype": "major",
    "start_provinces": 46,
    "start_income": 4830,
    "start_vp": 64,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Madagascar": {
    "pid": 31,
    "archetype": "minor",
    "start_provinces": 7,
    "start_income": 573,
    "start_vp": 10,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Mali": {
    "pid": 32,
    "archetype": "regional",
    "start_provinces": 37,
    "start_income": 5704,
    "start_vp": 57,
    "day13_vp": 36,
    "day13_provinces": 18,
    "opening": [
      "Konsolidasi + garnisun ibukota",
      "Ekspansi hanya ke AI terlemah",
      "Cari aliansi dengan superpower"
    ],
    "priorities": [
      "diplomasi/aliansi",
      "pertahanan ibukota",
      "ekonomi dulu"
    ],
    "benchmark": "Tertinggi teramati day-13: 36 VP / 18 provinsi."
  },
  "Mozambique": {
    "pid": 33,
    "archetype": "major",
    "start_provinces": 50,
    "start_income": 6240,
    "start_vp": 73,
    "day13_vp": 63,
    "day13_provinces": 41,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 63 VP / 41 provinsi."
  },
  "Namibia": {
    "pid": 34,
    "archetype": "major",
    "start_provinces": 45,
    "start_income": 5182,
    "start_vp": 63,
    "day13_vp": 93,
    "day13_provinces": 55,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 93 VP / 55 provinsi."
  },
  "Kenya": {
    "pid": 35,
    "archetype": "major",
    "start_provinces": 48,
    "start_income": 5557,
    "start_vp": 68,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Tunisia": {
    "pid": 36,
    "archetype": "minor",
    "start_provinces": 10,
    "start_income": 364,
    "start_vp": 13,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Afghanistan": {
    "pid": 37,
    "archetype": "major",
    "start_provinces": 48,
    "start_income": 6539,
    "start_vp": 71,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Azerbaijan": {
    "pid": 38,
    "archetype": "minor",
    "start_provinces": 8,
    "start_income": 2430,
    "start_vp": 11,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Georgia": {
    "pid": 39,
    "archetype": "minor",
    "start_provinces": 8,
    "start_income": 437,
    "start_vp": 11,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Iraq": {
    "pid": 40,
    "archetype": "major",
    "start_provinces": 41,
    "start_income": 6266,
    "start_vp": 63,
    "day13_vp": 55,
    "day13_provinces": 34,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 55 VP / 34 provinsi."
  },
  "Israel": {
    "pid": 41,
    "archetype": "minor",
    "start_provinces": 12,
    "start_income": 5509,
    "start_vp": 32,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Kyrgyzstan": {
    "pid": 42,
    "archetype": "minor",
    "start_provinces": 6,
    "start_income": 127,
    "start_vp": 6,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Mongolia": {
    "pid": 43,
    "archetype": "major",
    "start_provinces": 49,
    "start_income": 5318,
    "start_vp": 67,
    "day13_vp": 12,
    "day13_provinces": 2,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 12 VP / 2 provinsi."
  },
  "Myanmar": {
    "pid": 44,
    "archetype": "major",
    "start_provinces": 48,
    "start_income": 6503,
    "start_vp": 72,
    "day13_vp": 156,
    "day13_provinces": 112,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 156 VP / 112 provinsi."
  },
  "Nepal": {
    "pid": 45,
    "archetype": "minor",
    "start_provinces": 7,
    "start_income": 510,
    "start_vp": 10,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Oman": {
    "pid": 46,
    "archetype": "minor",
    "start_provinces": 9,
    "start_income": 437,
    "start_vp": 12,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Pakistan": {
    "pid": 47,
    "archetype": "major",
    "start_provinces": 46,
    "start_income": 6597,
    "start_vp": 70,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Philippines": {
    "pid": 48,
    "archetype": "regional",
    "start_provinces": 35,
    "start_income": 5702,
    "start_vp": 56,
    "day13_vp": 166,
    "day13_provinces": 81,
    "opening": [
      "Konsolidasi + garnisun ibukota",
      "Ekspansi hanya ke AI terlemah",
      "Cari aliansi dengan superpower"
    ],
    "priorities": [
      "diplomasi/aliansi",
      "pertahanan ibukota",
      "ekonomi dulu"
    ],
    "benchmark": "Tertinggi teramati day-13: 166 VP / 81 provinsi."
  },
  "Syria": {
    "pid": 49,
    "archetype": "regional",
    "start_provinces": 27,
    "start_income": 6475,
    "start_vp": 49,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Konsolidasi + garnisun ibukota",
      "Ekspansi hanya ke AI terlemah",
      "Cari aliansi dengan superpower"
    ],
    "priorities": [
      "diplomasi/aliansi",
      "pertahanan ibukota",
      "ekonomi dulu"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Tajikistan": {
    "pid": 50,
    "archetype": "minor",
    "start_provinces": 5,
    "start_income": 364,
    "start_vp": 8,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Yemen": {
    "pid": 51,
    "archetype": "minor",
    "start_provinces": 7,
    "start_income": 510,
    "start_vp": 10,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Belarus": {
    "pid": 52,
    "archetype": "major",
    "start_provinces": 45,
    "start_income": 6831,
    "start_vp": 69,
    "day13_vp": 267,
    "day13_provinces": 163,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 267 VP / 163 provinsi."
  },
  "Belgium": {
    "pid": 53,
    "archetype": "minor",
    "start_provinces": 8,
    "start_income": 437,
    "start_vp": 11,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Bulgaria": {
    "pid": 54,
    "archetype": "minor",
    "start_provinces": 9,
    "start_income": 510,
    "start_vp": 12,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Czechia": {
    "pid": 55,
    "archetype": "minor",
    "start_provinces": 8,
    "start_income": 364,
    "start_vp": 11,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Denmark": {
    "pid": 56,
    "archetype": "minor",
    "start_provinces": 8,
    "start_income": 573,
    "start_vp": 11,
    "day13_vp": 1,
    "day13_provinces": 1,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 1 VP / 1 provinsi."
  },
  "Finland": {
    "pid": 57,
    "archetype": "major",
    "start_provinces": 42,
    "start_income": 5064,
    "start_vp": 60,
    "day13_vp": 113,
    "day13_provinces": 67,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 113 VP / 67 provinsi."
  },
  "Greece": {
    "pid": 58,
    "archetype": "regional",
    "start_provinces": 36,
    "start_income": 5101,
    "start_vp": 55,
    "day13_vp": 276,
    "day13_provinces": 142,
    "opening": [
      "Konsolidasi + garnisun ibukota",
      "Ekspansi hanya ke AI terlemah",
      "Cari aliansi dengan superpower"
    ],
    "priorities": [
      "diplomasi/aliansi",
      "pertahanan ibukota",
      "ekonomi dulu"
    ],
    "benchmark": "Tertinggi teramati day-13: 276 VP / 142 provinsi."
  },
  "Hungary": {
    "pid": 59,
    "archetype": "minor",
    "start_provinces": 10,
    "start_income": 564,
    "start_vp": 13,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Iceland": {
    "pid": 60,
    "archetype": "minor",
    "start_provinces": 7,
    "start_income": 555,
    "start_vp": 10,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Ireland": {
    "pid": 61,
    "archetype": "minor",
    "start_provinces": 8,
    "start_income": 427,
    "start_vp": 11,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Netherlands": {
    "pid": 62,
    "archetype": "minor",
    "start_provinces": 10,
    "start_income": 573,
    "start_vp": 13,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Norway": {
    "pid": 63,
    "archetype": "major",
    "start_provinces": 45,
    "start_income": 5446,
    "start_vp": 64,
    "day13_vp": 65,
    "day13_provinces": 42,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 65 VP / 42 provinsi."
  },
  "Serbia": {
    "pid": 64,
    "archetype": "regional",
    "start_provinces": 34,
    "start_income": 4945,
    "start_vp": 52,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Konsolidasi + garnisun ibukota",
      "Ekspansi hanya ke AI terlemah",
      "Cari aliansi dengan superpower"
    ],
    "priorities": [
      "diplomasi/aliansi",
      "pertahanan ibukota",
      "ekonomi dulu"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Switzerland": {
    "pid": 65,
    "archetype": "minor",
    "start_provinces": 7,
    "start_income": 2430,
    "start_vp": 10,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Ukraine": {
    "pid": 66,
    "archetype": "superpower",
    "start_provinces": 62,
    "start_income": 6303,
    "start_vp": 85,
    "day13_vp": 2,
    "day13_provinces": 2,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Ekspansi 2-3 front sekaligus ke AI tetangga",
      "Arms Industry kedua setelah ekonomi jalan"
    ],
    "priorities": [
      "morale lintas front",
      "produksi udara/laut untuk proyeksi",
      "VP race"
    ],
    "benchmark": "Tertinggi teramati day-13: 2 VP / 2 provinsi."
  },
  "Costa Rica": {
    "pid": 67,
    "archetype": "minor",
    "start_provinces": 6,
    "start_income": 427,
    "start_vp": 9,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Cuba": {
    "pid": 68,
    "archetype": "regional",
    "start_provinces": 22,
    "start_income": 5045,
    "start_vp": 40,
    "day13_vp": 64,
    "day13_provinces": 26,
    "opening": [
      "Konsolidasi + garnisun ibukota",
      "Ekspansi hanya ke AI terlemah",
      "Cari aliansi dengan superpower"
    ],
    "priorities": [
      "diplomasi/aliansi",
      "pertahanan ibukota",
      "ekonomi dulu"
    ],
    "benchmark": "Tertinggi teramati day-13: 64 VP / 26 provinsi."
  },
  "Dominican Republic": {
    "pid": 69,
    "archetype": "minor",
    "start_provinces": 8,
    "start_income": 364,
    "start_vp": 11,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Guatemala": {
    "pid": 70,
    "archetype": "minor",
    "start_provinces": 7,
    "start_income": 510,
    "start_vp": 10,
    "day13_vp": 5,
    "day13_provinces": 5,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 5 VP / 5 provinsi."
  },
  "Haiti": {
    "pid": 71,
    "archetype": "minor",
    "start_provinces": 5,
    "start_income": 510,
    "start_vp": 8,
    "day13_vp": 4,
    "day13_provinces": 4,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 4 VP / 4 provinsi."
  },
  "Honduras": {
    "pid": 72,
    "archetype": "minor",
    "start_provinces": 6,
    "start_income": 437,
    "start_vp": 9,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Nicaragua": {
    "pid": 73,
    "archetype": "minor",
    "start_provinces": 6,
    "start_income": 510,
    "start_vp": 9,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Panama": {
    "pid": 74,
    "archetype": "minor",
    "start_provinces": 8,
    "start_income": 2430,
    "start_vp": 11,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Puerto Rico": {
    "pid": 75,
    "archetype": "minor",
    "start_provinces": 2,
    "start_income": 510,
    "start_vp": 5,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Bolivia": {
    "pid": 76,
    "archetype": "major",
    "start_provinces": 50,
    "start_income": 6538,
    "start_vp": 73,
    "day13_vp": 364,
    "day13_provinces": 218,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 364 VP / 218 provinsi."
  },
  "Chile": {
    "pid": 77,
    "archetype": "regional",
    "start_provinces": 28,
    "start_income": 5538,
    "start_vp": 48,
    "day13_vp": 3,
    "day13_provinces": 3,
    "opening": [
      "Konsolidasi + garnisun ibukota",
      "Ekspansi hanya ke AI terlemah",
      "Cari aliansi dengan superpower"
    ],
    "priorities": [
      "diplomasi/aliansi",
      "pertahanan ibukota",
      "ekonomi dulu"
    ],
    "benchmark": "Tertinggi teramati day-13: 3 VP / 3 provinsi."
  },
  "Ecuador": {
    "pid": 78,
    "archetype": "minor",
    "start_provinces": 6,
    "start_income": 437,
    "start_vp": 9,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Paraguay": {
    "pid": 79,
    "archetype": "minor",
    "start_provinces": 7,
    "start_income": 555,
    "start_vp": 10,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Uruguay": {
    "pid": 80,
    "archetype": "minor",
    "start_provinces": 7,
    "start_income": 510,
    "start_vp": 10,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Venezuela": {
    "pid": 81,
    "archetype": "major",
    "start_provinces": 48,
    "start_income": 6694,
    "start_vp": 71,
    "day13_vp": 4,
    "day13_provinces": 4,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 4 VP / 4 provinsi."
  },
  "New Zealand": {
    "pid": 82,
    "archetype": "regional",
    "start_provinces": 33,
    "start_income": 5274,
    "start_vp": 52,
    "day13_vp": 1,
    "day13_provinces": 1,
    "opening": [
      "Konsolidasi + garnisun ibukota",
      "Ekspansi hanya ke AI terlemah",
      "Cari aliansi dengan superpower"
    ],
    "priorities": [
      "diplomasi/aliansi",
      "pertahanan ibukota",
      "ekonomi dulu"
    ],
    "benchmark": "Tertinggi teramati day-13: 1 VP / 1 provinsi."
  },
  "Caribbean States": {
    "pid": 83,
    "archetype": "minor",
    "start_provinces": 6,
    "start_income": 2484,
    "start_vp": 9,
    "day13_vp": 5,
    "day13_provinces": 5,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 5 VP / 5 provinsi."
  },
  "Lithuania": {
    "pid": 84,
    "archetype": "minor",
    "start_provinces": 10,
    "start_income": 510,
    "start_vp": 13,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Angola": {
    "pid": 85,
    "archetype": "major",
    "start_provinces": 47,
    "start_income": 5395,
    "start_vp": 67,
    "day13_vp": 9,
    "day13_provinces": 3,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 9 VP / 3 provinsi."
  },
  "Ethiopia": {
    "pid": 86,
    "archetype": "major",
    "start_provinces": 43,
    "start_income": 6342,
    "start_vp": 66,
    "day13_vp": 39,
    "day13_provinces": 10,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 39 VP / 10 provinsi."
  },
  "Morocco": {
    "pid": 87,
    "archetype": "major",
    "start_provinces": 44,
    "start_income": 5673,
    "start_vp": 64,
    "day13_vp": 78,
    "day13_provinces": 48,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 78 VP / 48 provinsi."
  },
  "Nigeria": {
    "pid": 88,
    "archetype": "major",
    "start_provinces": 52,
    "start_income": 5445,
    "start_vp": 71,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Kazakhstan": {
    "pid": 89,
    "archetype": "major",
    "start_provinces": 54,
    "start_income": 6311,
    "start_vp": 75,
    "day13_vp": 170,
    "day13_provinces": 98,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Tertinggi teramati day-13: 170 VP / 98 provinsi."
  },
  "North Korea": {
    "pid": 90,
    "archetype": "regional",
    "start_provinces": 19,
    "start_income": 4191,
    "start_vp": 35,
    "day13_vp": 13,
    "day13_provinces": 8,
    "opening": [
      "Konsolidasi + garnisun ibukota",
      "Ekspansi hanya ke AI terlemah",
      "Cari aliansi dengan superpower"
    ],
    "priorities": [
      "diplomasi/aliansi",
      "pertahanan ibukota",
      "ekonomi dulu"
    ],
    "benchmark": "Tertinggi teramati day-13: 13 VP / 8 provinsi."
  },
  "South Korea": {
    "pid": 91,
    "archetype": "regional",
    "start_provinces": 18,
    "start_income": 4009,
    "start_vp": 34,
    "day13_vp": 1,
    "day13_provinces": 1,
    "opening": [
      "Konsolidasi + garnisun ibukota",
      "Ekspansi hanya ke AI terlemah",
      "Cari aliansi dengan superpower"
    ],
    "priorities": [
      "diplomasi/aliansi",
      "pertahanan ibukota",
      "ekonomi dulu"
    ],
    "benchmark": "Tertinggi teramati day-13: 1 VP / 1 provinsi."
  },
  "Vietnam": {
    "pid": 92,
    "archetype": "regional",
    "start_provinces": 38,
    "start_income": 6774,
    "start_vp": 62,
    "day13_vp": 73,
    "day13_provinces": 38,
    "opening": [
      "Konsolidasi + garnisun ibukota",
      "Ekspansi hanya ke AI terlemah",
      "Cari aliansi dengan superpower"
    ],
    "priorities": [
      "diplomasi/aliansi",
      "pertahanan ibukota",
      "ekonomi dulu"
    ],
    "benchmark": "Tertinggi teramati day-13: 73 VP / 38 provinsi."
  },
  "Austria": {
    "pid": 93,
    "archetype": "regional",
    "start_provinces": 31,
    "start_income": 5632,
    "start_vp": 52,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Konsolidasi + garnisun ibukota",
      "Ekspansi hanya ke AI terlemah",
      "Cari aliansi dengan superpower"
    ],
    "priorities": [
      "diplomasi/aliansi",
      "pertahanan ibukota",
      "ekonomi dulu"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Croatia": {
    "pid": 94,
    "archetype": "minor",
    "start_provinces": 8,
    "start_income": 437,
    "start_vp": 11,
    "day13_vp": 2,
    "day13_provinces": 2,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 2 VP / 2 provinsi."
  },
  "Portugal": {
    "pid": 95,
    "archetype": "minor",
    "start_provinces": 11,
    "start_income": 510,
    "start_vp": 14,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Romania": {
    "pid": 96,
    "archetype": "major",
    "start_provinces": 44,
    "start_income": 6540,
    "start_vp": 67,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Spain": {
    "pid": 97,
    "archetype": "major",
    "start_provinces": 46,
    "start_income": 6267,
    "start_vp": 70,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Peru": {
    "pid": 98,
    "archetype": "major",
    "start_provinces": 46,
    "start_income": 6584,
    "start_vp": 69,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Recruiting Office di semua kota hari-1",
      "Amankan region sendiri dulu dari AI",
      "Pilih satu front manusia setelah stack siap"
    ],
    "priorities": [
      "udara hari 3-4",
      "morale ekspansi",
      "satu front manusia"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Papua New Guinea": {
    "pid": 99,
    "archetype": "minor",
    "start_provinces": 7,
    "start_income": 437,
    "start_vp": 10,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Malaysia": {
    "pid": 100,
    "archetype": "minor",
    "start_provinces": 12,
    "start_income": 437,
    "start_vp": 15,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Taiwan": {
    "pid": 101,
    "archetype": "minor",
    "start_provinces": 3,
    "start_income": 364,
    "start_vp": 6,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Singapore": {
    "pid": 102,
    "archetype": "minor",
    "start_provinces": 1,
    "start_income": 2430,
    "start_vp": 4,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Sri Lanka": {
    "pid": 103,
    "archetype": "minor",
    "start_provinces": 4,
    "start_income": 510,
    "start_vp": 7,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Estonia": {
    "pid": 104,
    "archetype": "minor",
    "start_provinces": 12,
    "start_income": 364,
    "start_vp": 15,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Latvia": {
    "pid": 105,
    "archetype": "minor",
    "start_provinces": 11,
    "start_income": 510,
    "start_vp": 14,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Guyana": {
    "pid": 106,
    "archetype": "minor",
    "start_provinces": 4,
    "start_income": 482,
    "start_vp": 7,
    "day13_vp": 1,
    "day13_provinces": 1,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 1 VP / 1 provinsi."
  },
  "Suriname": {
    "pid": 107,
    "archetype": "minor",
    "start_provinces": 4,
    "start_income": 510,
    "start_vp": 7,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Jamaica": {
    "pid": 108,
    "archetype": "minor",
    "start_provinces": 3,
    "start_income": 437,
    "start_vp": 6,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Greenland": {
    "pid": 109,
    "archetype": "minor",
    "start_provinces": 2,
    "start_income": 364,
    "start_vp": 5,
    "day13_vp": 7,
    "day13_provinces": 2,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 7 VP / 2 provinsi."
  },
  "Bosnia": {
    "pid": 110,
    "archetype": "minor",
    "start_provinces": 8,
    "start_income": 364,
    "start_vp": 11,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Slovenia": {
    "pid": 111,
    "archetype": "minor",
    "start_provinces": 4,
    "start_income": 573,
    "start_vp": 7,
    "day13_vp": 9,
    "day13_provinces": 4,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 9 VP / 4 provinsi."
  },
  "Albania": {
    "pid": 112,
    "archetype": "minor",
    "start_provinces": 3,
    "start_income": 510,
    "start_vp": 6,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Slovakia": {
    "pid": 113,
    "archetype": "minor",
    "start_provinces": 7,
    "start_income": 500,
    "start_vp": 10,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Kuwait": {
    "pid": 114,
    "archetype": "minor",
    "start_provinces": 4,
    "start_income": 2430,
    "start_vp": 7,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Fiji": {
    "pid": 116,
    "archetype": "minor",
    "start_provinces": 2,
    "start_income": 364,
    "start_vp": 5,
    "day13_vp": 7,
    "day13_provinces": 2,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 7 VP / 2 provinsi."
  },
  "Solomon Islands": {
    "pid": 117,
    "archetype": "minor",
    "start_provinces": 1,
    "start_income": 45,
    "start_vp": 1,
    "day13_vp": 1,
    "day13_provinces": 1,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 1 VP / 1 provinsi."
  },
  "Malta": {
    "pid": 118,
    "archetype": "minor",
    "start_provinces": 1,
    "start_income": 2430,
    "start_vp": 4,
    "day13_vp": 6,
    "day13_provinces": 1,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 6 VP / 1 provinsi."
  },
  "Paracel Islands": {
    "pid": 119,
    "archetype": "minor",
    "start_provinces": 1,
    "start_income": 0,
    "start_vp": 1,
    "day13_vp": 1,
    "day13_provinces": 1,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 1 VP / 1 provinsi."
  },
  "Bangladesh": {
    "pid": 120,
    "archetype": "minor",
    "start_provinces": 7,
    "start_income": 364,
    "start_vp": 10,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Niger": {
    "pid": 121,
    "archetype": "minor",
    "start_provinces": 7,
    "start_income": 437,
    "start_vp": 10,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Zambia": {
    "pid": 123,
    "archetype": "minor",
    "start_provinces": 13,
    "start_income": 627,
    "start_vp": 16,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "South Sudan": {
    "pid": 124,
    "archetype": "minor",
    "start_provinces": 7,
    "start_income": 510,
    "start_vp": 10,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Turkmenistan": {
    "pid": 125,
    "archetype": "minor",
    "start_provinces": 8,
    "start_income": 510,
    "start_vp": 11,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Uzbekistan": {
    "pid": 126,
    "archetype": "minor",
    "start_provinces": 8,
    "start_income": 437,
    "start_vp": 11,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Mauritania": {
    "pid": 127,
    "archetype": "minor",
    "start_provinces": 13,
    "start_income": 555,
    "start_vp": 16,
    "day13_vp": 18,
    "day13_provinces": 13,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 18 VP / 13 provinsi."
  },
  "Lebanon": {
    "pid": 128,
    "archetype": "minor",
    "start_provinces": 5,
    "start_income": 510,
    "start_vp": 8,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Jordan": {
    "pid": 129,
    "archetype": "minor",
    "start_provinces": 3,
    "start_income": 437,
    "start_vp": 6,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Moldova": {
    "pid": 130,
    "archetype": "minor",
    "start_provinces": 6,
    "start_income": 437,
    "start_vp": 9,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Bermuda": {
    "pid": 131,
    "archetype": "minor",
    "start_provinces": 1,
    "start_income": 0,
    "start_vp": 1,
    "day13_vp": 1,
    "day13_provinces": 1,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 1 VP / 1 provinsi."
  },
  "Falklands": {
    "pid": 132,
    "archetype": "minor",
    "start_provinces": 2,
    "start_income": 63,
    "start_vp": 2,
    "day13_vp": 2,
    "day13_provinces": 2,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 2 VP / 2 provinsi."
  },
  "New Caledonia": {
    "pid": 133,
    "archetype": "minor",
    "start_provinces": 1,
    "start_income": 63,
    "start_vp": 1,
    "day13_vp": 1,
    "day13_provinces": 1,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 1 VP / 1 provinsi."
  },
  "Kerguelen Islands": {
    "pid": 134,
    "archetype": "minor",
    "start_provinces": 1,
    "start_income": 0,
    "start_vp": 1,
    "day13_vp": 1,
    "day13_provinces": 1,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 1 VP / 1 provinsi."
  },
  "Brunei": {
    "pid": 135,
    "archetype": "minor",
    "start_provinces": 1,
    "start_income": 510,
    "start_vp": 4,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Crimea": {
    "pid": 136,
    "archetype": "minor",
    "start_provinces": 2,
    "start_income": 437,
    "start_vp": 5,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Cabinda": {
    "pid": 138,
    "archetype": "minor",
    "start_provinces": 3,
    "start_income": 291,
    "start_vp": 6,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Botswana": {
    "pid": 139,
    "archetype": "minor",
    "start_provinces": 4,
    "start_income": 510,
    "start_vp": 7,
    "day13_vp": 9,
    "day13_provinces": 4,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 9 VP / 4 provinsi."
  },
  "KwaZulu-Natal": {
    "pid": 140,
    "archetype": "minor",
    "start_provinces": 4,
    "start_income": 510,
    "start_vp": 7,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Kashmir": {
    "pid": 141,
    "archetype": "minor",
    "start_provinces": 3,
    "start_income": 364,
    "start_vp": 6,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Cambodia": {
    "pid": 142,
    "archetype": "minor",
    "start_provinces": 6,
    "start_income": 437,
    "start_vp": 9,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Uyghur": {
    "pid": 143,
    "archetype": "minor",
    "start_provinces": 5,
    "start_income": 437,
    "start_vp": 8,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Patagonia": {
    "pid": 145,
    "archetype": "regional",
    "start_provinces": 19,
    "start_income": 437,
    "start_vp": 22,
    "day13_vp": 12,
    "day13_provinces": 12,
    "opening": [
      "Konsolidasi + garnisun ibukota",
      "Ekspansi hanya ke AI terlemah",
      "Cari aliansi dengan superpower"
    ],
    "priorities": [
      "diplomasi/aliansi",
      "pertahanan ibukota",
      "ekonomi dulu"
    ],
    "benchmark": "Tertinggi teramati day-13: 12 VP / 12 provinsi."
  },
  "Sudan": {
    "pid": 146,
    "archetype": "minor",
    "start_provinces": 14,
    "start_income": 573,
    "start_vp": 17,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Armenia": {
    "pid": 147,
    "archetype": "minor",
    "start_provinces": 2,
    "start_income": 0,
    "start_vp": 2,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Diego Garcia": {
    "pid": 148,
    "archetype": "minor",
    "start_provinces": 1,
    "start_income": 0,
    "start_vp": 1,
    "day13_vp": 1,
    "day13_provinces": 1,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 1 VP / 1 provinsi."
  },
  "Guam": {
    "pid": 149,
    "archetype": "minor",
    "start_provinces": 1,
    "start_income": 0,
    "start_vp": 1,
    "day13_vp": 1,
    "day13_provinces": 1,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 1 VP / 1 provinsi."
  },
  "Sao Tome and Principe": {
    "pid": 150,
    "archetype": "minor",
    "start_provinces": 1,
    "start_income": 364,
    "start_vp": 4,
    "day13_vp": 6,
    "day13_provinces": 1,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Tertinggi teramati day-13: 6 VP / 1 provinsi."
  },
  "Ulleungdo": {
    "pid": 151,
    "archetype": "minor",
    "start_provinces": 1,
    "start_income": 510,
    "start_vp": 4,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "Tsushima Island": {
    "pid": 152,
    "archetype": "minor",
    "start_provinces": 1,
    "start_income": 364,
    "start_vp": 4,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  },
  "North Macedonia": {
    "pid": 153,
    "archetype": "minor",
    "start_provinces": 7,
    "start_income": 482,
    "start_vp": 10,
    "day13_vp": 0,
    "day13_provinces": 0,
    "opening": [
      "Bertahan + bunker ibukota",
      "Satu stack kompak, jangan pecah",
      "Snipe VP dari perang orang lain"
    ],
    "priorities": [
      "supervivensi",
      "aliansi",
      "oportunisme VP"
    ],
    "benchmark": "Belum ada data akhir game."
  }
}


def get_doctrine(nation_or_pid):
    """Cari doktrin per nama (case-insensitive) atau playerID; tidak ada jadi None."""
    if isinstance(nation_or_pid, bool):
        return None
    if isinstance(nation_or_pid, int):
        for entry in NATIONS.values():
            if entry.get("pid") == nation_or_pid:
                return entry
        return None
    if isinstance(nation_or_pid, str):
        want = nation_or_pid.strip().casefold()
        if want:
            for name, entry in NATIONS.items():
                if name.casefold() == want:
                    return entry
            if want.isdigit():
                return get_doctrine(int(want))
    return None
