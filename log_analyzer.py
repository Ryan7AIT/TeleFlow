import os
import json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import argparse
import seaborn as sns
from collections import Counter
import numpy as np

class LogAnalyzer:
    """Analyze bot interaction logs and generate insights."""
    
    def __init__(self, log_dir="logs"):
        """Initialize the log analyzer.
        
        Args:
            log_dir: Directory containing log files
        """
        self.log_dir = log_dir
        self.df = None
        
    def load_logs(self, start_date=None, end_date=None, days=7):
        """Load logs from the specified date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format. If None, use end_date - days
            end_date: End date in YYYY-MM-DD format. If None, use today
            days: Number of days to analyze if start_date is None (default: 7)
            
        Returns:
            True if logs were loaded successfully, False otherwise
        """
        # Set default dates if not provided
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
            
        if start_date is None:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            start_dt = end_dt - timedelta(days=days-1)  # inclusive range
            start_date = start_dt.strftime("%Y-%m-%d")
        
        # Generate list of dates
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        date_list = []
        current_dt = start_dt
        while current_dt <= end_dt:
            date_list.append(current_dt.strftime("%Y-%m-%d"))
            current_dt += timedelta(days=1)
            
        # Read log files for each date
        all_logs = []
        
        for date in date_list:
            log_file = os.path.join(self.log_dir, f"bot_interactions_{date}.jsonl")
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            try:
                                log_entry = json.loads(line)
                                all_logs.append(log_entry)
                            except:
                                continue
                except Exception as e:
                    print(f"Error reading log file for {date}: {str(e)}")
        
        if not all_logs:
            print(f"No logs found for the date range {start_date} to {end_date}")
            return False
            
        # Convert to DataFrame for easier analysis
        self.df = pd.json_normalize(all_logs)
        
        # Convert timestamp to datetime
        if 'timestamp' in self.df.columns:
            self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
            self.df['date'] = self.df['timestamp'].dt.date
            self.df['hour'] = self.df['timestamp'].dt.hour
            
        print(f"Loaded {len(self.df)} log entries from {start_date} to {end_date}")
        return True
        
    def get_basic_stats(self):
        """Get basic statistics about the loaded logs.
        
        Returns:
            Dictionary containing basic statistics
        """
        if self.df is None or len(self.df) == 0:
            return {"error": "No logs loaded"}
            
        stats = {
            "total_interactions": len(self.df),
            "unique_users": self.df['user.user_id'].nunique(),
            "date_range": f"{self.df['date'].min()} to {self.df['date'].max()}",
            "avg_processing_time": self.df.get('matching.processing_time_ms', pd.Series()).mean(),
        }
        
        # Message types
        if 'message.type' in self.df.columns:
            stats["message_types"] = self.df['message.type'].value_counts().to_dict()
            
        # Languages
        if 'message.language' in self.df.columns:
            stats["languages"] = self.df['message.language'].value_counts().to_dict()
            
        # Commands matched
        if 'matching.command_matched' in self.df.columns:
            stats["commands_matched"] = self.df['matching.command_matched'].value_counts().to_dict()
            
        # Conversation stats
        if 'conversation.is_in_conversation' in self.df.columns:
            conv_count = self.df['conversation.is_in_conversation'].sum()
            stats["conversations"] = {
                "total": conv_count,
                "percentage": (conv_count / len(self.df)) * 100
            }
            
        # Error rate
        if 'error' in self.df.columns:
            error_count = self.df['error'].notna().sum()
            stats["errors"] = {
                "total": error_count,
                "percentage": (error_count / len(self.df)) * 100
            }
            
        return stats
        
    def activity_over_time(self, save_path=None):
        """Plot activity over time.
        
        Args:
            save_path: Path to save the plot to. If None, display the plot
            
        Returns:
            Figure object if save_path is not None, otherwise None
        """
        if self.df is None or len(self.df) == 0:
            print("No logs loaded")
            return None
            
        plt.figure(figsize=(12, 6))
        
        # Group by date and count interactions
        daily_counts = self.df.groupby('date').size()
        
        # Plot
        ax = daily_counts.plot(kind='bar', color='skyblue')
        plt.title('Bot Interactions per Day')
        plt.xlabel('Date')
        plt.ylabel('Number of Interactions')
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Add count labels on top of bars
        for i, count in enumerate(daily_counts):
            ax.text(i, count + 0.1, str(count), ha='center', va='bottom', fontweight='bold')
            
        if save_path:
            plt.savefig(save_path)
            plt.close()
            return ax.figure
        else:
            plt.show()
            return None
            
    def hourly_activity(self, save_path=None):
        """Plot activity by hour of day.
        
        Args:
            save_path: Path to save the plot to. If None, display the plot
            
        Returns:
            Figure object if save_path is not None, otherwise None
        """
        if self.df is None or len(self.df) == 0:
            print("No logs loaded")
            return None
            
        plt.figure(figsize=(12, 6))
        
        # Group by hour and count interactions
        hourly_counts = self.df.groupby('hour').size()
        
        # Plot
        ax = hourly_counts.plot(kind='bar', color='lightgreen')
        plt.title('Bot Interactions by Hour of Day')
        plt.xlabel('Hour')
        plt.ylabel('Number of Interactions')
        plt.xticks(range(24))
        plt.tight_layout()
        
        # Add count labels on top of bars
        for i, count in enumerate(hourly_counts):
            ax.text(i, count + 0.1, str(count), ha='center', va='bottom', fontweight='bold')
            
        if save_path:
            plt.savefig(save_path)
            plt.close()
            return ax.figure
        else:
            plt.show()
            return None
            
    def message_type_distribution(self, save_path=None):
        """Plot distribution of message types.
        
        Args:
            save_path: Path to save the plot to. If None, display the plot
            
        Returns:
            Figure object if save_path is not None, otherwise None
        """
        if self.df is None or len(self.df) == 0 or 'message.type' not in self.df.columns:
            print("No logs loaded or no message type data available")
            return None
            
        plt.figure(figsize=(10, 6))
        
        # Count message types
        type_counts = self.df['message.type'].value_counts()
        
        # Plot
        ax = type_counts.plot(kind='pie', autopct='%1.1f%%', colors=sns.color_palette("pastel"), 
                          textprops={'fontsize': 12})
        plt.title('Message Type Distribution')
        plt.ylabel('')
        plt.tight_layout()
            
        if save_path:
            plt.savefig(save_path)
            plt.close()
            return ax.figure
        else:
            plt.show()
            return None
            
    def language_distribution(self, save_path=None):
        """Plot distribution of message languages.
        
        Args:
            save_path: Path to save the plot to. If None, display the plot
            
        Returns:
            Figure object if save_path is not None, otherwise None
        """
        if self.df is None or len(self.df) == 0 or 'message.language' not in self.df.columns:
            print("No logs loaded or no language data available")
            return None
            
        plt.figure(figsize=(10, 6))
        
        # Count languages
        lang_counts = self.df['message.language'].value_counts()
        
        # Plot
        ax = lang_counts.plot(kind='pie', autopct='%1.1f%%', colors=sns.color_palette("Set3"), 
                          textprops={'fontsize': 12})
        plt.title('Message Language Distribution')
        plt.ylabel('')
        plt.tight_layout()
            
        if save_path:
            plt.savefig(save_path)
            plt.close()
            return ax.figure
        else:
            plt.show()
            return None
            
    def command_popularity(self, save_path=None, top_n=10):
        """Plot most popular commands.
        
        Args:
            save_path: Path to save the plot to. If None, display the plot
            top_n: Number of top commands to show
            
        Returns:
            Figure object if save_path is not None, otherwise None
        """
        if self.df is None or len(self.df) == 0 or 'matching.command_matched' not in self.df.columns:
            print("No logs loaded or no command data available")
            return None
            
        plt.figure(figsize=(12, 6))
        
        # Count commands, excluding None/NaN
        command_counts = self.df['matching.command_matched'].dropna().value_counts()
        
        # Get top N commands
        top_commands = command_counts.head(top_n)
        
        # Plot
        ax = top_commands.plot(kind='barh', color='coral')
        plt.title(f'Top {top_n} Most Popular Commands')
        plt.xlabel('Number of Uses')
        plt.ylabel('Command')
        plt.tight_layout()
        
        # Add count labels on bars
        for i, count in enumerate(top_commands):
            ax.text(count + 0.1, i, str(count), va='center', fontweight='bold')
            
        if save_path:
            plt.savefig(save_path)
            plt.close()
            return ax.figure
        else:
            plt.show()
            return None
            
    def processing_time_distribution(self, save_path=None):
        """Plot distribution of processing times.
        
        Args:
            save_path: Path to save the plot to. If None, display the plot
            
        Returns:
            Figure object if save_path is not None, otherwise None
        """
        if self.df is None or len(self.df) == 0 or 'matching.processing_time_ms' not in self.df.columns:
            print("No logs loaded or no processing time data available")
            return None
            
        plt.figure(figsize=(12, 6))
        
        # Plot histogram of processing times
        sns.histplot(self.df['matching.processing_time_ms'].dropna(), kde=True, bins=30)
        plt.title('Distribution of Message Processing Times')
        plt.xlabel('Processing Time (ms)')
        plt.ylabel('Frequency')
        plt.tight_layout()
            
        if save_path:
            plt.savefig(save_path)
            plt.close()
            return plt.gcf()
        else:
            plt.show()
            return None
            
    def user_engagement(self, save_path=None, top_n=10):
        """Plot user engagement (most active users).
        
        Args:
            save_path: Path to save the plot to. If None, display the plot
            top_n: Number of top users to show
            
        Returns:
            Figure object if save_path is not None, otherwise None
        """
        if self.df is None or len(self.df) == 0 or 'user.user_id' not in self.df.columns:
            print("No logs loaded or no user data available")
            return None
            
        plt.figure(figsize=(12, 6))
        
        # Count interactions per user
        user_counts = self.df['user.user_id'].value_counts()
        
        # Get top N users
        top_users = user_counts.head(top_n)
        
        # Anonymize user IDs for the plot
        anonymized = [f"User {i+1}" for i in range(len(top_users))]
        
        # Plot
        plt.barh(anonymized, top_users.values, color='purple')
        plt.title(f'Top {top_n} Most Active Users')
        plt.xlabel('Number of Interactions')
        plt.ylabel('User')
        plt.tight_layout()
        
        # Add count labels on bars
        for i, count in enumerate(top_users.values):
            plt.text(count + 0.1, i, str(count), va='center', fontweight='bold')
            
        if save_path:
            plt.savefig(save_path)
            plt.close()
            return plt.gcf()
        else:
            plt.show()
            return None
            
    def matching_effectiveness(self, save_path=None):
        """Plot distribution of matching scores to evaluate effectiveness.
        
        Args:
            save_path: Path to save the plot to. If None, display the plot
            
        Returns:
            Figure object if save_path is not None, otherwise None
        """
        if self.df is None or len(self.df) == 0 or 'matching.score' not in self.df.columns:
            print("No logs loaded or no matching score data available")
            return None
            
        plt.figure(figsize=(12, 6))
        
        # Plot histogram of matching scores
        sns.histplot(self.df['matching.score'].dropna(), kde=True, bins=30)
        plt.title('Distribution of Command Matching Scores')
        plt.xlabel('Match Score')
        plt.ylabel('Frequency')
        
        # Add vertical line at the threshold
        plt.axvline(x=0.65, color='r', linestyle='--', label='Threshold (0.65)')
        plt.legend()
        
        plt.tight_layout()
            
        if save_path:
            plt.savefig(save_path)
            plt.close()
            return plt.gcf()
        else:
            plt.show()
            return None
            
    def matching_method_comparison(self, save_path=None):
        """Compare effectiveness of different matching methods.
        
        Args:
            save_path: Path to save the plot to. If None, display the plot
            
        Returns:
            Figure object if save_path is not None, otherwise None
        """
        if (self.df is None or len(self.df) == 0 or 
            'matching.method' not in self.df.columns or 
            'matching.score' not in self.df.columns):
            print("No logs loaded or no matching method data available")
            return None
            
        plt.figure(figsize=(12, 6))
        
        # Group by matching method and get average score
        method_scores = self.df.groupby('matching.method')['matching.score'].agg(['mean', 'std', 'count'])
        
        # Plot
        ax = method_scores['mean'].plot(kind='bar', yerr=method_scores['std'], capsize=5, 
                                     color=['blue', 'green', 'orange'])
        plt.title('Comparison of Command Matching Methods')
        plt.xlabel('Matching Method')
        plt.ylabel('Average Match Score')
        plt.ylim(0, 1)
        
        # Add count and mean labels
        for i, (mean, count) in enumerate(zip(method_scores['mean'], method_scores['count'])):
            ax.text(i, mean + 0.05, f"n={count}\nμ={mean:.2f}", ha='center', va='bottom', fontweight='bold')
            
        plt.tight_layout()
            
        if save_path:
            plt.savefig(save_path)
            plt.close()
            return ax.figure
        else:
            plt.show()
            return None
            
    def generate_report(self, output_dir="reports", days=7):
        """Generate a comprehensive report with all visualizations.
        
        Args:
            output_dir: Directory to save reports to
            days: Number of days to analyze
            
        Returns:
            Path to the report directory
        """
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Generate timestamp for report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = os.path.join(output_dir, f"bot_report_{timestamp}")
        os.makedirs(report_dir)
        
        # Load recent logs if not already loaded
        if self.df is None:
            self.load_logs(days=days)
            
        if self.df is None or len(self.df) == 0:
            with open(os.path.join(report_dir, "report.txt"), 'w') as f:
                f.write("No logs available for analysis.")
            return report_dir
            
        # Get basic stats
        stats = self.get_basic_stats()
        
        # Save stats as JSON
        with open(os.path.join(report_dir, "stats.json"), 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=4)
            
        # Generate and save all visualizations
        self.activity_over_time(save_path=os.path.join(report_dir, "activity_over_time.png"))
        self.hourly_activity(save_path=os.path.join(report_dir, "hourly_activity.png"))
        self.message_type_distribution(save_path=os.path.join(report_dir, "message_types.png"))
        self.language_distribution(save_path=os.path.join(report_dir, "languages.png"))
        self.command_popularity(save_path=os.path.join(report_dir, "popular_commands.png"))
        self.processing_time_distribution(save_path=os.path.join(report_dir, "processing_times.png"))
        self.user_engagement(save_path=os.path.join(report_dir, "user_engagement.png"))
        self.matching_effectiveness(save_path=os.path.join(report_dir, "matching_scores.png"))
        self.matching_method_comparison(save_path=os.path.join(report_dir, "matching_methods.png"))
        
        # Generate HTML report
        self._generate_html_report(report_dir, stats)
        
        print(f"Report generated at {report_dir}")
        return report_dir
        
    def _generate_html_report(self, report_dir, stats):
        """Generate an HTML report with all visualizations and stats.
        
        Args:
            report_dir: Directory to save the report to
            stats: Statistics dictionary
        """
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Telegram Bot Analytics Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
                h1, h2 { color: #333; }
                .container { max-width: 1200px; margin: 0 auto; }
                .stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }
                .stat-card { background-color: #f5f5f5; border-radius: 8px; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .stat-value { font-size: 24px; font-weight: bold; color: #2c3e50; margin: 10px 0; }
                .stat-label { color: #7f8c8d; font-size: 14px; }
                .chart-container { margin-bottom: 30px; background-color: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .chart-container img { width: 100%; height: auto; }
                .timestamp { color: #7f8c8d; font-size: 14px; text-align: center; margin-top: 30px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Telegram Bot Analytics Report</h1>
                <p>Generated on: {timestamp}</p>
                
                <h2>Summary Statistics</h2>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-label">Total Interactions</div>
                        <div class="stat-value">{total_interactions}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Unique Users</div>
                        <div class="stat-value">{unique_users}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Analyzed Period</div>
                        <div class="stat-value" style="font-size: 18px;">{date_range}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Average Processing Time</div>
                        <div class="stat-value">{avg_processing_time:.2f} ms</div>
                    </div>
                </div>
                
                <h2>User Activity</h2>
                <div class="chart-container">
                    <h3>Daily Activity</h3>
                    <img src="activity_over_time.png" alt="Activity Over Time">
                </div>
                
                <div class="chart-container">
                    <h3>Hourly Activity</h3>
                    <img src="hourly_activity.png" alt="Hourly Activity">
                </div>
                
                <div class="chart-container">
                    <h3>Most Active Users</h3>
                    <img src="user_engagement.png" alt="User Engagement">
                </div>
                
                <h2>Message Analysis</h2>
                <div class="chart-container">
                    <h3>Message Type Distribution</h3>
                    <img src="message_types.png" alt="Message Types">
                </div>
                
                <div class="chart-container">
                    <h3>Language Distribution</h3>
                    <img src="languages.png" alt="Language Distribution">
                </div>
                
                <h2>Command Analysis</h2>
                <div class="chart-container">
                    <h3>Most Popular Commands</h3>
                    <img src="popular_commands.png" alt="Popular Commands">
                </div>
                
                <h2>Performance Analysis</h2>
                <div class="chart-container">
                    <h3>Processing Time Distribution</h3>
                    <img src="processing_times.png" alt="Processing Times">
                </div>
                
                <div class="chart-container">
                    <h3>Command Matching Score Distribution</h3>
                    <img src="matching_scores.png" alt="Matching Scores">
                </div>
                
                <div class="chart-container">
                    <h3>Matching Method Comparison</h3>
                    <img src="matching_methods.png" alt="Matching Methods">
                </div>
                
                <div class="timestamp">Generated on {timestamp}</div>
            </div>
        </body>
        </html>
        """
        
        # Format with stats
        formatted_html = html.format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_interactions=stats.get("total_interactions", 0),
            unique_users=stats.get("unique_users", 0),
            date_range=stats.get("date_range", "N/A"),
            avg_processing_time=stats.get("avg_processing_time", 0)
        )
        
        # Write to file
        with open(os.path.join(report_dir, "report.html"), 'w', encoding='utf-8') as f:
            f.write(formatted_html)


def main():
    """Command-line interface for log analysis."""
    parser = argparse.ArgumentParser(description="Analyze Telegram bot logs")
    parser.add_argument("--log-dir", default="logs", help="Directory containing log files")
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=7, help="Number of days to analyze if start-date is not specified")
    parser.add_argument("--report", action="store_true", help="Generate a full report")
    parser.add_argument("--output-dir", default="reports", help="Directory to save reports to")
    
    args = parser.parse_args()
    
    analyzer = LogAnalyzer(log_dir=args.log_dir)
    
    if args.report:
        analyzer.generate_report(output_dir=args.output_dir, days=args.days)
    else:
        # Load logs
        if not analyzer.load_logs(start_date=args.start_date, end_date=args.end_date, days=args.days):
            return
            
        # Print basic stats
        stats = analyzer.get_basic_stats()
        print("\n===== Basic Statistics =====")
        print(f"Total interactions: {stats['total_interactions']}")
        print(f"Unique users: {stats['unique_users']}")
        print(f"Date range: {stats['date_range']}")
        
        if "message_types" in stats:
            print("\nMessage types:")
            for msg_type, count in stats["message_types"].items():
                print(f"  {msg_type}: {count}")
                
        if "languages" in stats:
            print("\nLanguages:")
            for lang, count in stats["languages"].items():
                print(f"  {lang}: {count}")
                
        if "commands_matched" in stats:
            print("\nTop 5 commands:")
            for cmd, count in list(sorted(stats["commands_matched"].items(), key=lambda x: x[1], reverse=True))[:5]:
                print(f"  {cmd}: {count}")
                
        print("\nShowing visualizations...")
        analyzer.activity_over_time()
        analyzer.command_popularity()
        analyzer.language_distribution()
        analyzer.user_engagement()
        
if __name__ == "__main__":
    main() 