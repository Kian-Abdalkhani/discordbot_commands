# Changelog

## [0.6.0](https://github.com/Kian-Abdalkhani/discordbot_commands/compare/discordbotv0.5.0...discordbotv0.6.0) (2025-09-13)


### Features

* Added /give_money command so that admins can adjust player's balance without having to down the server. ([73e073d](https://github.com/Kian-Abdalkhani/discordbot_commands/commit/73e073dc2b0d0570bc8e12507bed6c0e4adbc9b8))


### Bug Fixes

* Configured so that admins can no longer manually start horse races ([c312f67](https://github.com/Kian-Abdalkhani/discordbot_commands/commit/c312f67b6837e1cb34ea3ba36995d1219233633a))

## [0.5.0](https://github.com/Kian-Abdalkhani/discordbot_commands/compare/discordbotv0.4.0...discordbotv0.5.0) (2025-09-06)


### Features

* add database for tracking cash flow and P/L ([0fd4dc0](https://github.com/Kian-Abdalkhani/discordbot_commands/commit/0fd4dc03f62863fb722abeac6c86f733cfbe2eec))


### Bug Fixes

* added logistic curve to horse_race_manager.py that is configured within settings.py ([d4674eb](https://github.com/Kian-Abdalkhani/discordbot_commands/commit/d4674eb2c65b1a05f9afc3723a582c5137dfb18f))
* Updated last place payout for fairness ([4b56578](https://github.com/Kian-Abdalkhani/discordbot_commands/commit/4b5657881a41e0eb99c1025532afdc8afd49aecc))


### Code Refactoring

* grouped settings.py configurations by command group ([d750bf5](https://github.com/Kian-Abdalkhani/discordbot_commands/commit/d750bf5629f04f3b2258e85c63e1343924fa55d4))

## [0.4.0](https://github.com/Kian-Abdalkhani/discordbot_commands/compare/discordbotv0.3.0...discordbotv0.4.0) (2025-09-04)


### Features

* Add horse nickname manager and update blackjack stats handling ([5f5c16e](https://github.com/Kian-Abdalkhani/discordbot_commands/commit/5f5c16ead9cbdaeff1011b56e855c27d9e9d9530))
* Added dividend payments to the bot (`/dividend_calendar`, `/dividend_info`, and `/dividend_history`) along with showing projected dividends and yields within the `/portfolio` command. ([ca5a8b7](https://github.com/Kian-Abdalkhani/discordbot_commands/commit/ca5a8b738d8df9cfae42b7bf4e1c40690a9f884c))


### Bug Fixes

* Use direct modal response instead of followup for betting flow ([07e0b7f](https://github.com/Kian-Abdalkhani/discordbot_commands/commit/07e0b7f91f7f20c5c44539e50007e4101f8cc6bf))


### Code Refactoring

* remove LLM tests and update project structure ([b9c7c39](https://github.com/Kian-Abdalkhani/discordbot_commands/commit/b9c7c3932f5191dc6ae73f383d3fdc1b4b5f32ec))
