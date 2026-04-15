## ADDED Requirements

### Requirement: Root README language pair
The repository SHALL provide a Chinese companion README at the repository root alongside the English root README, and both documents SHALL expose direct language-switch links.

#### Scenario: Operator opens the default root README
- **WHEN** an operator opens `README.md` at the repository root
- **THEN** the document identifies the project as `JusticeThemis`, acts as the default bootstrap entrypoint, and links directly to `README.zh.md`

#### Scenario: Operator opens the Chinese companion README
- **WHEN** an operator opens `README.zh.md` at the repository root
- **THEN** the document acts as the Chinese bootstrap companion, identifies the project as `JusticeThemis`, and links directly back to `README.md`

### Requirement: README structural parity contract
The English and Chinese root README documents SHALL preserve one aligned bootstrap structure for product identity, runtime contract, environment guidance, startup instructions, canonical upstream and synchronization guidance, repository hygiene, auth surfaces, smoke checks, and acceptance criteria.

#### Scenario: Maintainer validates section parity
- **WHEN** the README parity verification runs
- **THEN** it confirms that the English and Chinese README documents expose the same ordered section identities for the required bootstrap topics

#### Scenario: Maintainer validates critical bootstrap content parity
- **WHEN** the README parity verification checks required bootstrap invariants
- **THEN** it confirms that both documents include the canonical startup command, the canonical regression command, the canonical upstream repository reference, and the non-Git convergence warning

### Requirement: GitHub publication parity
The README language pair SHALL be published together whenever the bootstrap package is moved from this local standalone directory into the Git-backed convergence workspace for `Etherstrings/JusticeThemis`.

#### Scenario: Maintainer prepares a GitHub-ready convergence branch
- **WHEN** local bootstrap documentation changes are imported into the isolated Git-backed convergence workspace
- **THEN** both `README.md` and `README.zh.md` are present at the repository root and preserve their language-switch links

#### Scenario: Maintainer reviews README publication guidance
- **WHEN** a maintainer uses the bootstrap documentation to prepare a GitHub update
- **THEN** the documentation states that this local directory is not itself a Git worktree and that GitHub publication must happen through the isolated convergence workflow
