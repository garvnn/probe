# Attacker A system prompt

Owner: Shreyas. Used for the forger loop and hardening.

TODO: write the prompt. It must:

- Explain the goal: fabricate one trial site that passes site-level checks AND shows a strong drug effect.
- State what the attacker knows: the protocol, aggregate stats a site investigator could plausibly know, and the names of checks that fired last round.
- Require a single Python file defining `generate_site(context) -> dict[str, list[dict]]`, using only numpy, pandas, datetime, with output matching docs/schema.md.
