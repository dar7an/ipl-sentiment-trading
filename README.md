# IPL Sentiment Trading Analysis

**An AI-powered signal generator for cricket betting markets that synthesizes live match data, betting odds, and social media sentiment to identify trading opportunities.**

---

## What It Does

This system acts as a "super-analyst" for professional cricket traders. Every 5 minutes during an IPL match, it:

1. **Analyzes On-Field Performance**: Tracks ball-by-ball action including Dot Ball %, Boundary %, Partnership Runs, and Run Rate.
2. **Monitors Betting Odds**: Captures real-time odds movements from bookmakers.
3. **Gauges Fan Sentiment**: Processes thousands of Reddit comments using VADER sentiment analysis to detect crowd psychology.
4. **Generates Trading Signals**: Uses Google Gemini AI to synthesize all three data sources and produce a "Trader Sentiment" verdict (Bullish/Bearish/Neutral) for each team.

The AI is **context-aware**, meaning it remembers the narrative arc of the match and can detect momentum shifts, trend reversals, and divergences between odds and sentiment.

---

## Key Features

- **Hybrid NLP Pipeline**: Local VADER for quantitative scoring + Gemini 2.5 Flash for qualitative context analysis
- **Advanced Cricket Metrics**: Dot Ball %, Boundary %, Partnership Runs, Run Rate
- **Context-Aware Analysis**: Tracks match history to identify momentum shifts and sentiment reversals
- **Real-Time Processing**: Designed for low-latency signals during live matches
- **Trader-Centric Output**: Provides actionable insights with clear Bullish/Bearish verdicts

---

## Installation

### Prerequisites
- Python 3.9+
- Google Gemini API key ([Get one here](https://ai.google.dev/))

### Setup
```bash
# Clone the repository
git clone https://github.com/dar7an/ipl-sentiment-betting.git
cd ipl-sentiment-betting

# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install the package (enables the CLI command)
pip install -e .

# Set your API key
export GOOGLE_API_KEY="your_api_key_here"
```

---

## Usage

### Basic Command
```bash
ipl-analyze data/chunks/1.json output.md
```

**Arguments:**
- `input_file`: Path to JSON file with match data (e.g., `data/chunks/1.json`)
- `output_file`: Path to save the Markdown analysis (e.g., `output.md`)

### Alternative (Without Installation)
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
python3 -m ipl_sentiment_betting.main data/chunks/1.json output.md
```

---

## Repository Structure

```
ipl-sentiment-betting/
├── src/ipl_sentiment_betting/    # Application code
│   ├── core/                      # Core analysis logic (MatchAnalyzer)
│   ├── analysis/                  # Sentiment analysis tools (VADER)
│   ├── utils/                     # Configuration and utilities
│   └── main.py                    # CLI entry point
├── data/                          # Raw match data
│   ├── chunks/                    # Processed 5-min interval data
│   ├── balls/                     # Ball-by-ball data
│   ├── odds/                      # Betting odds data
│   └── comments/                  # Reddit comments
├── data_collection/               # Scraping scripts
│   ├── sportmonks/                # Sportmonks API scripts
│   ├── the_odds_api/              # The Odds API scripts
│   └── reddit/                    # Reddit scraping
├── tests/                         # Unit tests
├── pyproject.toml                 # Project metadata & dependencies
└── README.md                      # This file
```

---

## How It Works

### 1. Data Collection (Not Automated)
The `data_collection/` directory contains scripts to fetch:
- **Ball-by-ball data** from [Sportmonks](https://www.sportmonks.com/)
- **Betting odds** from [The Odds API](https://the-odds-api.com/)
- **Fan comments** from Reddit

These scripts produce the JSON files stored in `data/`.

### 2. Analysis Pipeline
The `ipl-analyze` command processes a match JSON file:

1. **Local Sentiment Analysis**: VADER calculates sentiment scores for all comments, producing:
   - Average Sentiment Score (-1 to 1)
   - Distribution (Positive/Negative/Neutral counts)
   - Top 3 Bullish and Bearish comments

2. **Ball-by-Ball Summary**: Calculates:
   - Run Rate, Wickets
   - Dot Ball %, Boundary %, Partnership Runs

3. **LLM Synthesis**: Feeds all data to Gemini AI with:
   - Match Narrative History (last 3 intervals)
   - Current interval data (odds, sentiment, cricket metrics)
   - Instructions to identify divergences and provide Trader Sentiment

4. **Output**: Generates a Markdown report with interval-by-interval breakdowns.

---

## Example Output

```markdown
## Interval: chunk_2

### Ball-by-Ball Summary
Summary for Chennai Super Kings: 42 runs from 30 balls (RR: 8.40). Wickets: 1.
Metrics: Dot Ball %: 23.3%, Boundary %: 26.7%, Partnership Runs (this interval): 28.

### Odds Summary
Latest odds (2024-03-22 08:00:13 PM IST): Chennai Super Kings: 1.77, Royal Challengers Bangalore: 2.0

### AI-Generated Analysis
**Match Interval Report: Royal Challengers Bengaluru vs Chennai Super Kings**

This interval shows CSK maintaining strong favoritism (1.77 odds) with solid on-field performance (8.40 RR, 26.7% boundaries). Fan sentiment remains marginally positive at 0.06. Compared to the previous interval, CSK's odds lengthened slightly from 1.75 to 1.77, while RCB shortened from 2.1 to 2.0, indicating a negligible market adjustment. The sentiment-odds alignment is weak, as fan comments remain detached from match dynamics.

**Trader Sentiment:**
- Chennai Super Kings: **Bullish** (Strong value odds, solid metrics)
- Royal Challengers Bangalore: **Bearish** (Underdog status persists)
```

---

## Data Sources

This project would not have been possible without:
- [The Odds API](https://the-odds-api.com/) — Historical betting odds
- [Sportmonks](https://www.sportmonks.com/) — Ball-by-ball match data
- [Reddit](https://www.reddit.com) — Fan sentiment via comments

Thank you to these platforms for their support.

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Contributing

This is a personal portfolio project, but suggestions and improvements are welcome! Feel free to open an issue or submit a pull request.
