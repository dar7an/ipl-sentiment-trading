import json
import time
import pandas as pd
import google.generativeai as genai
from typing import List, Dict, Any, Optional
from ipl_sentiment_betting.utils.config import Config
from ipl_sentiment_betting.analysis.sentiment import SentimentAnalyzer

class MatchAnalyzer:
    """
    A class to encapsulate the entire IPL match analysis process, using the
    Google AI API for all generative tasks.
    """

    def __init__(self):
        """
        Initializes the analyzer, configuring the Google AI API client.
        """
        Config.validate()
        genai.configure(api_key=Config.GOOGLE_API_KEY)
        
        # Initialize local sentiment analyzer
        self.sentiment_analyzer = SentimentAnalyzer()
        
        system_prompt = (
            "You are a professional sports-data analyst for a high-frequency trading firm. Your audience is expert cricket traders who need to cut through noise to find actionable signals. Your task is to provide objective, data-driven summaries of IPL match intervals.\n\n"
            "**CRITICAL RULES:**\n"
            "1. **ANALYZE ALL DATA:** You will be given on-field action (with advanced metrics), odds, and a pre-calculated sentiment summary. Your summary MUST synthesize all three.\n"
            "2. **TRADER SENTIMENT:** You must explicitly state the 'Trader Sentiment' (Bullish/Bearish/Neutral) for each team based on the combined signals.\n"
            "3. **ADHERE TO DATA:** Your analysis must be strictly based on the data provided. Do NOT invent information.\n"
            "4. **THINK LIKE A TRADER:** Focus on momentum shifts, partnership building, pressure (dot ball %), and significant odds drifts.\n"
            "5. **MAINTAIN T20 CONTEXT:** Interpret data within the match phase (Powerplay, Middle, Death).\n"
            "6. **BE OBJECTIVE & CONCISE:** Use neutral, analytical language. Avoid hype."
        )
        
        print("Initializing Google AI Generative Model...")
        self.generative_model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            system_instruction=system_prompt
        )
        print("Google AI Model initialized successfully.")


    def generate_api_response(self, user_prompt: str) -> str:
        """Generates a response from the Google AI API."""
        try:
            response = self.generative_model.generate_content(user_prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Error calling Google AI API: {e}")
            return "Error: Could not generate a summary from the AI model."

    def format_odds(self, odds_data: Optional[List[Dict[str, Any]]]) -> str:
        """Formats odds data from the chunk structure."""
        if not odds_data or not isinstance(odds_data, list) or not odds_data[0].get("odds"):
            return "No odds data available for this interval."
        try:
            latest_odds_entry = odds_data[0]["odds"]
            odds_str = ", ".join([f"{o['name']}: {o['price']}" for o in latest_odds_entry])
            update_time = odds_data[0].get("last_update", "unknown time")
            return f"Latest odds ({update_time}): {odds_str}"
        except (KeyError, IndexError, TypeError) as e:
            print(f"Warning: Could not parse odds data: {e} - Data: {odds_data}")
            return "Could not parse odds data."

    def summarize_ball_by_ball(self, balls_data: List[Dict[str, Any]], team1_info: Dict[str, Any], team2_info: Dict[str, Any]) -> str:
        """
        Summarizes key events from the ball-by-ball data list ('balls' key),
        including player-team associations and advanced metrics.
        """
        if not balls_data or not isinstance(balls_data, list):
            return "No balls recorded in this interval."
        
        player_to_team = {}
        for player in team1_info.get("xi", []): player_to_team[player] = team1_info["name"]
        for player in team2_info.get("xi", []): player_to_team[player] = team2_info["name"]

        event_summary = []
        total_runs, wickets, fours, sixes, wides, dots, valid_balls_count = (0, 0, 0, 0, 0, 0, 0)
        batting_team_name = "Unknown"
        
        # Track partnership for this chunk (simplified)
        current_partnership_runs = 0

        for ball_info in balls_data:
            try:
                score_info = ball_info.get("score", {})
                ball_num = ball_info.get("ball", "?")
                runs = score_info.get("runs", 0)
                is_wicket = score_info.get("is_wicket", False)
                is_four = score_info.get("four", False)
                is_six = score_info.get("six", False)
                is_valid_ball = score_info.get("ball", False)
                score_name = score_info.get("name", "").lower()
                
                batsman_name = ball_info.get("batsman", {}).get("fullname", "Unknown Batsman")
                bowler_name = ball_info.get("bowler", {}).get("fullname", "Unknown Bowler")
                batting_team_name = ball_info.get("name", batting_team_name)

                batsman_team = player_to_team.get(batsman_name, "")
                bowler_team = player_to_team.get(bowler_name, "")

                batsman_str = f"{batsman_name} ({batsman_team})" if batsman_team else batsman_name
                bowler_str = f"{bowler_name} ({bowler_team})" if bowler_team else bowler_name

                total_runs += runs
                current_partnership_runs += runs
                
                if is_valid_ball: valid_balls_count += 1
                if "wide" in score_name: wides += 1
                
                event_desc = None
                if is_wicket:
                    wickets += 1
                    current_partnership_runs = 0 # Reset partnership on wicket
                    event_desc = f"WICKET at {ball_num}! {batsman_str} out b {bowler_str}."
                elif is_six:
                    sixes += 1
                    event_desc = f"SIX at {ball_num}! by {batsman_str} off {bowler_str}."
                elif is_four:
                    fours += 1
                    event_desc = f"FOUR at {ball_num}! by {batsman_str} off {bowler_str}."
                elif is_valid_ball and runs == 0:
                    dots += 1
                
                if event_desc: event_summary.append(event_desc)
            except Exception as e:
                print(f"Warning: Error processing ball data: {e} - Data: {ball_info}")
                continue
        
        run_rate = (total_runs / (valid_balls_count / 6)) if valid_balls_count > 0 else 0
        dot_percentage = (dots / valid_balls_count * 100) if valid_balls_count > 0 else 0
        boundary_percentage = ((fours + sixes) / valid_balls_count * 100) if valid_balls_count > 0 else 0
        
        overall_summary = (
            f"Summary for {batting_team_name}: {total_runs} runs from {valid_balls_count} balls "
            f"(RR: {run_rate:.2f}). Wickets: {wickets}.\n"
            f"Metrics: Dot Ball %: {dot_percentage:.1f}%, Boundary %: {boundary_percentage:.1f}%, "
            f"Partnership Runs (this interval): {current_partnership_runs}."
        )
        
        full_summary = overall_summary
        if event_summary:
            full_summary += "\nKey events: " + " | ".join(event_summary)
        
        return full_summary

    def analyze_sentiment(self, comments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyzes sentiment of comments locally.
        Returns a summary dictionary with scores and representative comments.
        """
        if not comments:
            return {"summary": "No comments available.", "average_score": 0.0}

        scores = []
        valid_comments = []
        
        for c in comments:
            text = c.get("comment")
            if text and text != "[deleted]":
                score = self.sentiment_analyzer.get_sentiment_score(text)
                scores.append(score)
                valid_comments.append({"text": text, "score": score})
        
        if not scores:
            return {"summary": "No valid comments for analysis.", "average_score": 0.0}
            
        avg_score = sum(scores) / len(scores)
        positive_count = sum(1 for s in scores if s > 0.05)
        negative_count = sum(1 for s in scores if s < -0.05)
        neutral_count = len(scores) - positive_count - negative_count
        
        # Select representative comments (highest/lowest scores)
        valid_comments.sort(key=lambda x: x["score"])
        top_positive = valid_comments[-3:] if valid_comments[-1]["score"] > 0.5 else []
        top_negative = valid_comments[:3] if valid_comments[0]["score"] < -0.5 else []
        
        summary_str = (
            f"Sentiment Analysis (VADER): Average Score: {avg_score:.2f} (-1 to 1). "
            f"Distribution: {positive_count} Positive, {negative_count} Negative, {neutral_count} Neutral."
        )
        
        return {
            "summary": summary_str,
            "average_score": avg_score,
            "top_positive": [c["text"] for c in top_positive],
            "top_negative": [c["text"] for c in top_negative]
        }

    def generate_match_update(self, ball_summary: str, odds_summary: str, sentiment_data: Dict[str, Any], team1_name: str, team2_name: str, match_history: List[str] = []) -> str:
        """Generates a professional, data-driven summary of a match interval using the Google AI API."""
        
        data_points = []
        if "No balls recorded" not in ball_summary:
            data_points.append(f"### On-Field Action (with Metrics)\n{ball_summary}")
        
        if "No odds data available" not in odds_summary:
            data_points.append(f"### Odds Analysis\n{odds_summary}")

        data_points.append(f"### Fan Sentiment Analysis\n{sentiment_data['summary']}")
        
        if sentiment_data.get("top_positive"):
            data_points.append(f"**Top Bullish Comments:**\n" + "\n".join([f"- {c}" for c in sentiment_data["top_positive"]]))
        if sentiment_data.get("top_negative"):
            data_points.append(f"**Top Bearish Comments:**\n" + "\n".join([f"- {c}" for c in sentiment_data["top_negative"]]))
        
        if not data_points:
            return "No new data available in this interval to generate an update."

        # Format history for context
        history_context = ""
        if match_history:
            history_context = "### Match Narrative History (Previous Intervals)\n"
            for i, update in enumerate(match_history[-3:]): # Keep last 3 updates for relevance
                history_context += f"**Interval {i+1}:** {update}\n\n"

        user_prompt_content = "\n\n".join(data_points)
        user_prompt = f"""
        **Match Interval Report**
        **Teams:** {team1_name} vs {team2_name}

        {history_context}

        ### Current Interval Data
        {user_prompt_content}

        **Your Task:**
        Distill the provided data into a concise summary for a professional cricket trader. 
        1. **Synthesize** the on-field metrics (Dot %, Boundaries) with the sentiment score.
        2. **Identify** if the fan sentiment aligns with the odds movement.
        3. **Compare** the current state to the *Match Narrative History*. Have the odds shifted? Has sentiment reversed?
        4. **Provide** a clear "Trader Sentiment" verdict.
        """
        
        return self.generate_api_response(user_prompt)

    def process_match_data(self, match_data: Dict[str, Any], team1_info: Dict[str, Any], team2_info: Dict[str, Any]) -> pd.DataFrame:
        """Processes all data chunks for a match."""
        all_match_updates = []

        chunks = match_data.get('chunks', {})
        for i, chunk in enumerate(chunks):
            chunk_id = chunk.get("name", f"chunk_{i+1}")
            print(f"\n--- Processing Chunk {i+1}/{len(chunks)} ({chunk_id}) ---")

            # Prepare data for the API
            comments_in_chunk = chunk.get("comments", [])
            odds_summary = self.format_odds(chunk.get("odds"))
            ball_summary = self.summarize_ball_by_ball(chunk.get("balls"), team1_info, team2_info)
            sentiment_data = self.analyze_sentiment(comments_in_chunk)
            
            # Match Update Generation
            update_text = self.generate_match_update(
                ball_summary, odds_summary, sentiment_data, team1_info['name'], team2_info['name'],
                match_history=[u["analysis_update"] for u in all_match_updates]
            )
            print(f"  - Model Update: {update_text.replace(chr(10), ' ')[0:100]}...")

            all_match_updates.append({
                "chunk_id": chunk_id,
                "ball_by_ball_summary": ball_summary,
                "odds_summary": odds_summary,
                "sentiment_summary": sentiment_data['summary'],
                "analysis_update": update_text,
            })
            
            # Add a delay to respect API rate limits
            time.sleep(1)

        return pd.DataFrame(all_match_updates)
