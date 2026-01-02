# Dashboard Package

This package contains the Streamlit-based dashboard for Smart Finanza.

## Structure

```
dashboard/
├── __init__.py          # Package marker, exports main()
├── backend.py           # Cached backend initialization (DB, LLM, Tracker)
├── layout.py            # Main layout coordinator and entry point
├── query.py             # Query delegation layer (delegates to db.py and llm.py)
├── tab_dashboard.py     # Dashboard tab (metrics, charts)
├── tab_data_manager.py  # Data Manager tab (file upload, data editor)
├── tab_ai_analyst.py    # AI Analyst tab (natural language queries)
└── tab_rules.py         # Rules tab (teach categorization rules)
```

## Key Files

### `backend.py`
- **Purpose**: Initialize and cache backend resources
- **Uses**: `@st.cache_resource` to ensure DB, LLM, and Tracker are created once
- **Why needed**: Prevents re-initialization on every Streamlit rerun

### `layout.py`
- **Purpose**: Main entry point and layout coordinator
- **Contains**: `main()` function that orchestrates all tabs
- **Why needed**: Central place for page structure

### `__init__.py`
- **Purpose**: Makes dashboard a proper Python package
- **Exports**: `main()` for easy importing
- **Why needed**: Required for `from dashboard import main`

## Architecture Principles

1. **Single Responsibility**: 
   - DB operations only in `db.py`
   - LLM operations only in `llm.py`
   - Dashboard just coordinates and displays

2. **Separation of Concerns**:
   - Each tab is its own module
   - `layout.py` orchestrates tabs
   - `query.py` provides a thin delegation layer

3. **Caching**:
   - Backend resources (DB, LLM, Tracker) are cached via `@st.cache_resource`

## Running the Dashboard

From the backend directory:

```bash
make run
```

Or directly:

```bash
uv run streamlit run src/main.py
```

## Adding New Tabs

1. Create a new file `tab_<name>.py`
2. Define a render function: `def render_<name>_tab(args):`
3. Import and call it in `layout.py`
