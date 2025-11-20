import argparse
import json
import sys
from ipl_sentiment_betting.core.analyzer import MatchAnalyzer

def save_results_as_markdown(updates_df, output_path, team1_name, team2_name):
    """Saves the analysis results to a Markdown file."""
    print("\n--- Saving Results ---")
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# Match Analysis: {team1_name} vs {team2_name}\n\n")
            
            for _, row in updates_df.iterrows():
                f.write(f"## Interval: {row['chunk_id']}\n\n")

                f.write("### Ball-by-Ball Summary\n")
                f.write(f"{row['ball_by_ball_summary']}\n\n")

                f.write("### Odds Summary\n")
                f.write(f"{row['odds_summary']}\n\n")

                f.write("### AI-Generated Analysis\n")
                f.write(f"{row['analysis_update']}\n\n")

                f.write("---\n\n")
        print(f"Results saved to {output_path}")
    except Exception as e:
        print(f"Error saving results to Markdown file: {e}")

def main():
    """Main function to run the enhanced analysis."""
    parser = argparse.ArgumentParser(description="Run IPL Match Analysis.")
    parser.add_argument("input_path", type=str, help="Path to the input JSON chunk file.")
    parser.add_argument("output_path", type=str, help="Path to save the output analysis Markdown file.")
    args = parser.parse_args()

    try:
        analyzer = MatchAnalyzer()
    except Exception as e:
        print(f"Failed to initialize analyzer: {e}")
        sys.exit(1)

    print(f"Processing {args.input_path}...")
    try:
        with open(args.input_path, 'r') as f:
            match_data = json.load(f)
    except Exception as e:
        print(f"Error reading or parsing JSON file: {e}")
        sys.exit(1)

    # Attempt to dynamically load team info from the JSON structure
    match_info = match_data.get("match_info", {})
    team1_info = match_info.get("team1", {"name": "Team 1", "xi": []})
    team2_info = match_info.get("team2", {"name": "Team 2", "xi": []})
    print(f"Loaded team info: {team1_info['name']} vs {team2_info['name']}")
    
    updates_df = analyzer.process_match_data(
        match_data, team1_info, team2_info
    )

    save_results_as_markdown(updates_df, args.output_path, team1_info['name'], team2_info['name'])

    print("\nAnalysis complete.")

if __name__ == "__main__":
    main()
