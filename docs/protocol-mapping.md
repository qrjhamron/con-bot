# Protocol audit — con-bot 2.0.3

Checked on 9 October 2026 using the authenticated game state, the English
`getContentItems` catalog, and the public official desktop client.
Construction-queue rows (cos/prs, mode 3/4, completed evidence) added
10 October 2026 from city construction state and cancel paths:

- [Desktop client](https://www.conflictnations.com/clients/con-client-desktop/con-client-desktop_live/index.html)
- [Client bundle](https://www.conflictnations.com/clients/con-client-desktop/con-client-desktop_live/js/doradohup.714e5d.js): build `v374.p`.
- The current bundle matches the previously downloaded bundle. No newer public
  desktop build was found at this URL; updating the bot corrects its adapters.

## Mapping corrections

| Field or ID | Meaning from the official client/catalog |
| --- | --- |
| Army `s` | Stack size, never activity |
| Army `c` | Command queue; a first `gc` with arrival time indicates movement |
| Army `fs` | Fight status; 1 combat, 2 bombardment, 3/4 patrol, 7 bombing |
| Army action `u` | Required unit array, wrapped as `[Lultshared.warfare.UltUnit;` |
| `gc` serialization | `@c`, `sp`, `tp`; timing/speed fields are server state |
| `ac` | Uses `targetPos`; province attacks use target unit ID 0 |
| Relation -2 | War, unsigned byte 254, base64 `/g==` |
| Relation 4 | Military pact, never war |
| Unit 2039 | Motorized Infantry, land |
| Unit 2075 | Combat Recon Vehicle, land |
| Unit 2103 | Towed Artillery, land |
| Unit 2175 | Air Superiority Fighter, air |
| Building 2250 | Army Base |
| Building 2255 | Air Base |
| Building 2270 | Recruiting Office |
| Building 2245/2246 | Population levels 6/7 |
| Resource 2 | Components |
| Resource 4 | Rare Materials |
| Resource 5/6 | Fuel/Electronics |
| Province `cos` | In-progress construction: `u` template + `t` end time; `None` entries are free build slots |
| Province `prs` / `pi` | Unit production queue / in-progress item (`u.unit.t` type) |
| Mode 3 / mode 4 | Cancel building / production at `slot`; verified only when that slot reads free (`None`), never from missing queue data |
| Mode 1 evidence | `completed` is true only when the building sits in `us`; a `cos`-only entry is still under construction |

IDs vary across doctrines, unit levels and catalogs. Runtime names come from
the authenticated catalog; production/construction IDs must match a city's
actual queueable templates. Research choices use current prerequisites and
the doctrine inferred from owned units.

## Evidence of execution

A response code of 1 records acceptance only. The agent reads fresh game state
and checks the requested route, attack target, diplomatic relation, construction,
production, or research before recording completion. It polls state at most
three times and never retries the mutation. A verified construction whose
building is still only in `cos` is reported as under construction, not finished.
A cancelled slot is confirmed only when the slot itself reads free.

An unchanged or unreadable state records an unknown outcome and stops the task.
The same unresolved action is blocked across tasks and restarts. An existing
manual route is reported as already applied, without sending it again.
Actions without an implemented state verifier cannot be reported as completed.

Offline regressions exercise payloads, false acknowledgments, manual routes,
rejections, interrupted refreshes, and type mapping. Live diagnosis reads state
only; it does not replay the owner's movement orders.
