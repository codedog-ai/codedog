# CHANGELOG



## v0.5.3 (2023-08-02)

### Fix

* fix(actor): :bug: fix report changes file print table even with no file change (#21)

fix(actor): :bug: fix report changes file print table even with no file change ([`577745f`](https://github.com/codedog-ai/codedog/commit/577745fbd93c876bfcdcbe48a755a3db2856ff72))

* fix(chain): :bug: fix async call broken (#20)

fix(chain): :bug: fix async call broken ([`7b29ddd`](https://github.com/codedog-ai/codedog/commit/7b29ddd51068987e5df0a95c4e86e9a3bb1544a2))


## v0.5.2 (2023-08-02)

### Build

* build: fix build ([`abbf4fc`](https://github.com/codedog-ai/codedog/commit/abbf4fc05c44360bc61fdf7a71c72dd587fc21c1))

* build: :memo: improve documentation ([`fd0d8bf`](https://github.com/codedog-ai/codedog/commit/fd0d8bf36796f48bfd721879583bff680de1656b))

### Chore

* chore(release): release version v0.5.2 ([`29e647c`](https://github.com/codedog-ai/codedog/commit/29e647cec3669ceac7947648b73b087bef306a24))

* chore(release): release version v0.5.1 ([`f10558e`](https://github.com/codedog-ai/codedog/commit/f10558eb0b42068ccf0df341463a6604d7c1574f))

* chore: :arrow_up: ([`cc2d3f9`](https://github.com/codedog-ai/codedog/commit/cc2d3f971acfb48d9aeb6d2614831964ed874fd6))

### Ci

* ci: :green_heart: add poetry cache ([`5c977de`](https://github.com/codedog-ai/codedog/commit/5c977dec2c7dce01da3ddeadd15116fc1df8e483))

### Fix

* fix(Chain): :bug: fix asyncio missing await ([`3845382`](https://github.com/codedog-ai/codedog/commit/3845382499b65b2d60b58ffbaa7fcf7f522ef859))

* fix(Chain): :bug: Fix callback manager usage

Other changes: fix build issue and remove logging related codes in server example. ([`452b483`](https://github.com/codedog-ai/codedog/commit/452b48374c3705d4baf335c2da8df36866f91d27))

### Refactor

* refactor: :heavy_minus_sign: remove useless code ([`c404d7f`](https://github.com/codedog-ai/codedog/commit/c404d7fde2e7997fbefecbe915c4cf632e80a9e8))

### Unknown

* Update README.md ([`d2609c5`](https://github.com/codedog-ai/codedog/commit/d2609c559924f3b4c5670ff4a17c8e820a035379))

* Build (#12)

* refactor: :fire: Remove useless dependency and prepare for build ([`45768a7`](https://github.com/codedog-ai/codedog/commit/45768a784e1b3788a73d38c487036a2b8faac7eb))


## v0.5.0 (2023-07-29)

### Feature

* feat: :sparkles: read github private key from env ([`1c388f3`](https://github.com/codedog-ai/codedog/commit/1c388f3bc5117f89fb8fa68d239d3eb837eeec7d))

### Fix

* fix(PR Summary): :bug: Handle github event none value ([`7fbe9f3`](https://github.com/codedog-ai/codedog/commit/7fbe9f3ff216cdbfc4f1681c1dfb8990ea46f9d1))

### Unknown

* 0.5.0

chore(release): release version 0.5.0 ([`4e74e2e`](https://github.com/codedog-ai/codedog/commit/4e74e2e1d7efb048bea2d5fd7bade5dda8739841))

* Use New Implementation and remove server things. (#11)

* feat(PR Reivew): :sparkles: New implementation of Pull Request Review Chains and Reports ([`449adb8`](https://github.com/codedog-ai/codedog/commit/449adb8bf32335bd3f8d4759198b79acd5372350))

* Merge pull request #10 from codedog-ai/feature/read-private-key-from-env

feat: :sparkles: read github private key from env ([`7bc2c84`](https://github.com/codedog-ai/codedog/commit/7bc2c845a0cf8a0275b6df23a839e1ba4ef7d026))

* Feature: Github Retriever and PR Summary Chain (#9)

* feat: :sparkles: Retriever, Github Retriever, PR Summary Chain

1. Extract code files (by suffix whitelist) from pr change list
2. Summarize changed file list and there status
3. Summarize PR with description, PR Type, major files ([`3105595`](https://github.com/codedog-ai/codedog/commit/310559526480b3be18e3cdce8c3da1a33b1dc654))

* Update issue templates ([`b62ddea`](https://github.com/codedog-ai/codedog/commit/b62ddea805d72c1f3e82134f91a10318c4c96104))

* Feature/#1/localization (#7)

* feat: :globe_with_meridians: Localization: support review in English ([`b8efbbc`](https://github.com/codedog-ai/codedog/commit/b8efbbcd1aabd1512fafd1ed3beb9e7a3f5f6423))


## v0.4.0 (2023-07-20)

### Fix

* fix: :bug: Unable to fetch installation_id ([`f170bfb`](https://github.com/codedog-ai/codedog/commit/f170bfb161b65c384bcb0e94a51717bfbd4cae12))

### Unknown

* 0.4.0

chore(release): release version 0.4.0 ([`961ec78`](https://github.com/codedog-ai/codedog/commit/961ec785de4a08289f37fd81a7c9da0a68ab8de2))


## v0.3.0 (2023-07-20)

### Feature

* feat: :sparkles: support github app ([`3834bfc`](https://github.com/codedog-ai/codedog/commit/3834bfc7a085317d7e7cf16c7199067fd84cf36f))

### Unknown

* 0.3.0

chore(release): release version 0.3.0 ([`4399b23`](https://github.com/codedog-ai/codedog/commit/4399b2324bf55a998f6daa76ea7101c8396b826b))

* Merge pull request #6 from codedog-ai/feature/support-github-app

feat: :sparkles: support github app ([`23b70ae`](https://github.com/codedog-ai/codedog/commit/23b70aef0af2f36ab558f624976d19970638aa23))


## v0.2.2 (2023-07-18)

### Fix

* fix: :bug: disable openai proxy configuration ([`1008ba2`](https://github.com/codedog-ai/codedog/commit/1008ba2267f4a4fe7754fa7807ef028563f7e643))

### Unknown

* 0.2.2

chore(release): release version 0.2.2 ([`424f8a3`](https://github.com/codedog-ai/codedog/commit/424f8a3ef450885b2b0762c704c51e01ce1efe8e))


## v0.2.1 (2023-07-18)

### Ci

* ci: :green_heart: fix ci ([`04b7026`](https://github.com/codedog-ai/codedog/commit/04b7026c77a609b98e4d95a60402cdc718b27f8d))

* ci: :construction_worker: add version commit message ([`3fcdb95`](https://github.com/codedog-ai/codedog/commit/3fcdb951a68e2b95f6056228c815ad3d2c1c6a84))

### Fix

* fix: :bug: fix openai proxy init ([`3368bd4`](https://github.com/codedog-ai/codedog/commit/3368bd4a6ea4013e96587efd4871a720e00f27ff))

### Unknown

* 0.2.1

chore(release): release version 0.2.1 ([`542ac48`](https://github.com/codedog-ai/codedog/commit/542ac487e6d173758a879030125dbc93b455250f))


## v0.2.0 (2023-07-14)

### Ci

* ci: :green_heart: upload test report ([`a5599cd`](https://github.com/codedog-ai/codedog/commit/a5599cdabd68e6a6fc75442b8d9fd8c0fde2d53f))

* ci: :green_heart: fix permission issue ([`be63524`](https://github.com/codedog-ai/codedog/commit/be635242211578ac6ae1f80931d92723897eb09f))

* ci: 👷 setup auto tagging and release (#4) ([`158ddc2`](https://github.com/codedog-ai/codedog/commit/158ddc217044c739c7cb324c29f6cecfd8071af8))

* ci: :construction_worker: setup semantic release ([`126d3a0`](https://github.com/codedog-ai/codedog/commit/126d3a06866816c07aed6208f8c88d54c0caeeba))

* ci: :green_heart: config semantic release ([`d07566a`](https://github.com/codedog-ai/codedog/commit/d07566a5de24c6cbd0383603777083d88612e5e4))

* ci: :green_heart: update poetry version ([`8127d3e`](https://github.com/codedog-ai/codedog/commit/8127d3e47f1e8be6ff51fe9e8ee7358aef00b68a))

### Feature

* feat(telemetry): :sparkles: collect gpt api cost (#2)

* feat(telemetry): :sparkles: collect gpt api cost ([`14dc92c`](https://github.com/codedog-ai/codedog/commit/14dc92c73b0ade2c6e6754f0a941995f33b1726f))

* feat: :tada: init commit ([`1d6fc33`](https://github.com/codedog-ai/codedog/commit/1d6fc33aefb697fd9fa2423867206906c79094b2))

### Unknown

* 0.2.0

Automatically generated by python-semantic-release ([`c52bbd6`](https://github.com/codedog-ai/codedog/commit/c52bbd69083663a3ad53991621b2ce25ae7bca62))

* Fix/housekeeping (#3)

housekeeping ([`4d11ac7`](https://github.com/codedog-ai/codedog/commit/4d11ac7d9d3a5a48f2eb2ca11ceb7499ecf7905c))

* housekeeping ([`d5ad367`](https://github.com/codedog-ai/codedog/commit/d5ad36797c99f46ad3747ae7de3af5575192be66))

* 0.1.0

Automatically generated by python-semantic-release ([`d0f10da`](https://github.com/codedog-ai/codedog/commit/d0f10da954d654d91f0191ddaeaf5c02a05c3c42))
