# Building and Publishing Documentation

This guide explains how to build and publish the Gilt documentation using MkDocs.

## Prerequisites

Install MkDocs and the Material theme:

```bash
# Activate your virtual environment
source .venv/bin/activate

# Install documentation dependencies
pip install mkdocs mkdocs-material mkdocs-awesome-pages-plugin
```

## Building Documentation

### Local Preview

Build and serve the documentation locally:

```bash
# From the project root
mkdocs serve
```

This starts a local server at `http://127.0.0.1:8000/` with auto-reload on changes.

### Build Static Site

Generate the static HTML site:

```bash
mkdocs build
```

This creates a `site/` directory with the complete static website.

## Documentation Structure

```
docs/
├── index.md                          # Home page
├── getting-started.md                # Getting started guide
├── user/                             # User documentation
│   ├── index.md                      # User guide overview
│   ├── installation.md               # Installation instructions
│   ├── cli/                          # CLI documentation
│   │   ├── index.md                  # CLI overview
│   │   ├── accounts.md               # Account management
│   │   ├── importing.md              # Data import
│   │   ├── categorization.md         # Categorization guide
│   │   ├── budgeting.md              # Budgeting guide
│   │   └── viewing.md                # Viewing & reporting
│   ├── gui/                          # GUI documentation
│   │   ├── index.md                  # GUI overview
│   │   ├── installation.md           # GUI installation
│   │   ├── dashboard.md              # Dashboard guide
│   │   ├── transactions.md           # Transactions view
│   │   ├── categories.md             # Categories management
│   │   ├── budget.md                 # Budget tracking
│   │   └── importing.md              # Import wizard
│   └── workflows/                    # Common workflows
│       ├── initial-setup.md          # Initial setup
│       ├── monthly-review.md         # Monthly review
│       └── budget-tracking.md        # Budget tracking
└── developer/                        # Developer documentation
    ├── index.md                      # Developer guide overview
    ├── architecture/                 # Architecture docs
    │   ├── system-design.md          # System design
    │   ├── project-structure.md      # Project structure
    │   └── data-model.md             # Data model
    ├── technical/                    # Technical details
    │   ├── cli-implementation.md     # CLI implementation
    │   ├── gui-implementation.md     # GUI implementation
    │   ├── budgeting-system.md       # Budgeting system
    │   └── transfer-linking.md       # Transfer linking
    ├── development/                  # Development guides
    │   ├── setup.md                  # Development setup
    │   ├── testing.md                # Testing guide
    │   └── contributing.md           # Contributing guidelines
    └── history/                      # Implementation history
        ├── phase2-summary.md         # Phase 2 summary
        ├── phase3-summary.md         # Phase 3 summary
        └── phase4-summary.md         # Phase 4 summary
```

## Writing Documentation

### Markdown Features

The documentation uses MkDocs Material theme with these extensions:

**Admonitions**:
```markdown
!!! note "Title"
    This is a note

!!! warning "Warning Title"
    This is a warning

!!! tip "Pro Tip"
    This is a helpful tip
```

**Code Blocks**:
````markdown
```python
def example():
    pass
```

```bash
gilt categorize --help
```
````

**Tables**:
```markdown
| Column 1 | Column 2 |
|----------|----------|
| Value 1  | Value 2  |
```

**Internal Links**:
```markdown
[Link text](relative-path.md)
[Link to section](page.md#section)
```

### Best Practices

1. **Clear Headings**: Use descriptive, hierarchical headings
2. **Code Examples**: Include practical, runnable examples
3. **Cross-References**: Link related pages
4. **Screenshots**: Consider adding screenshots for GUI docs
5. **Keep Current**: Update docs when code changes

## Publishing

### GitHub Pages

To publish on GitHub Pages:

```bash
# Build and deploy
mkdocs gh-deploy
```

This builds the site and pushes to the `gh-pages` branch.

### Custom Hosting

To host elsewhere:

1. Build the site: `mkdocs build`
2. Upload the `site/` directory to your web server
3. Configure web server to serve `site/index.html`

## Configuration

The documentation is configured in `mkdocs.yml`:

```yaml
site_name: Gilt - Privacy-First Financial Management
site_description: Local-only, privacy-first financial management tool

theme:
  name: material
  palette:
    - scheme: default  # Light mode
    - scheme: slate    # Dark mode

nav:
  # Navigation structure defined here
```

### Customization

**Theme Colors**:
Edit `theme.palette.primary` and `theme.palette.accent` in `mkdocs.yml`.

**Navigation**:
Edit the `nav` section to change menu structure.

**Features**:
Enable/disable features in `theme.features`.

## Maintenance

### Adding New Pages

1. Create markdown file in appropriate directory
2. Add to navigation in `mkdocs.yml`
3. Link from related pages
4. Build and verify

### Updating Content

1. Edit markdown files
2. Preview with `mkdocs serve`
3. Commit changes
4. Rebuild/republish

### Checking Links

Test all internal links:

```bash
# Build site
mkdocs build

# Check for broken links (requires additional tool)
# Consider using a link checker tool
```

## Todo

The following documentation files are stub placeholders and need content:

**User CLI Guides**:
- [ ] `docs/user/cli/accounts.md` - Account management commands
- [ ] `docs/user/cli/importing.md` - Import and ingest commands
- [ ] `docs/user/cli/categorization.md` - Categorization commands
- [ ] `docs/user/cli/budgeting.md` - Budget commands
- [ ] `docs/user/cli/viewing.md` - Viewing and reporting commands

**User GUI Guides**:
- [ ] `docs/user/gui/installation.md` - GUI installation details
- [ ] `docs/user/gui/dashboard.md` - Dashboard usage
- [ ] `docs/user/gui/transactions.md` - Transactions view usage
- [ ] `docs/user/gui/categories.md` - Categories management
- [ ] `docs/user/gui/budget.md` - Budget tracking
- [ ] `docs/user/gui/importing.md` - Import wizard usage

**User Workflows**:
- [ ] `docs/user/workflows/initial-setup.md` - Initial setup workflow
- [ ] `docs/user/workflows/monthly-review.md` - Monthly review workflow
- [ ] `docs/user/workflows/budget-tracking.md` - Budget tracking workflow

**Developer Architecture**:
- [ ] `docs/developer/architecture/project-structure.md` - Project structure
- [ ] `docs/developer/architecture/data-model.md` - Data model details

**Developer Technical**:
- [ ] `docs/developer/technical/cli-implementation.md` - CLI implementation
- [ ] `docs/developer/technical/gui-implementation.md` - GUI implementation
- [ ] `docs/developer/technical/transfer-linking.md` - Transfer linking

**Developer Development**:
- [ ] `docs/developer/development/setup.md` - Development setup
- [ ] `docs/developer/development/testing.md` - Testing guide
- [ ] `docs/developer/development/contributing.md` - Contributing guidelines

These files can be created by extracting content from:
- `README.md`
- `BUDGETING.md`
- `GUI_README.md`
- `PHASE2_SUMMARY.md`
- `PHASE3_SUMMARY.md`
- `PHASE4_SUMMARY.md`
- `Qt.md`
- `CLAUDE.md`

## Resources

- [MkDocs Documentation](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
- [Markdown Guide](https://www.markdownguide.org/)
