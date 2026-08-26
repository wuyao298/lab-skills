# lab-skills

A collection of agent skills for scientific / lab research workflows. Each skill under
[`skills/`](skills/) is self-contained and follows the standard agent skill layout
(`SKILL.md` + runnable library + tests + references).

## Skills index

| Skill | Domain | One-liner |
|---|---|---|
| [matplot-publisher](skills/matplot-publisher/) | Scientific plotting | Turn `.mat` oscilloscope waveforms (up to ~100M points) into publication-grade PDF + 600 DPI PNG, with a 6-layer pipeline (perceive → interpret → decide → validate → execute → crystallize) and mandatory preview confirmation. |
| [adhd-brain-dump](skills/adhd-brain-dump/) | ADHD task management | Non-judgmental 3-stage pipeline for ADHD brains: brain-dump triage (「倾倒：」) → big-task splitting into milestones & micro-steps with interactive context gathering (「拆分：」) → auto-sync tasks, subtasks, notes and due dates to Microsoft To Do via `microsoft-todo-cli`. |

More skills will land here as they mature.

## Layout

```
lab-skills/
├── README.md                     # this file
├── LICENSE                       # MIT
├── .gitignore
└── skills/
    └── <skill-name>/
        ├── SKILL.md              # entry point — description, triggers, steps, rules
        ├── README.md             # install / CLI / API quickstart
        ├── requirements.txt
        ├── <package>/            # runnable library
        ├── scripts/              # CLI / selfcheck helpers
        ├── references/           # long-form rules & specs
        ├── tests/
        ├── examples/
        └── profiles/             # success-profile archives (per-skill)
```

## Conventions

- One skill per directory under `skills/`. No cross-skill imports.
- `SKILL.md` front-matter carries `name` + `description` (description doubles as the
  trigger list — keep it scannable).
- Runtime artefacts (preview PNGs, intermediate `.npy`, generated PDFs) are
  git-ignored; reproduce them from the skill itself.
- Tests are local to each skill. Run from the skill root:
  `cd skills/<skill-name> && pytest`.

## Contributing

1. Add your skill under `skills/<your-skill>/`.
2. Make sure `SKILL.md` follows the schema (`name`, `description`, `## 步骤` / steps).
3. Open a PR. Include the skill's own `requirements.txt` (don't share a top-level one).

## License

[MIT](LICENSE).
