import requests
from bs4 import BeautifulSoup
import statbotics
import sys
import json

def get_team_info(team_num, year=2025):
    """Get all team information and return as a dictionary"""
    sb = statbotics.Statbotics()
    result = {}
    
    try:
        # Get team name
        team_year_data = sb.get_team_year(team_num, year)
        result['name'] = team_year_data.get('name', '')
        
        # Get EPA data
        epa_data = team_year_data.get("epa", {})
        result['epa'] = epa_data.get('total_points', {}).get('mean', None)
        
        # Get ranking data
        ranks = epa_data.get('ranks', {})
        result['state_rank'] = ranks.get('state', {}).get('rank', None)
        result['state_total'] = ranks.get('state', {}).get('team_count', None)
        result['country_rank'] = ranks.get('country', {}).get('rank', None)
        result['country_total'] = ranks.get('country', {}).get('team_count', None)
        result['world_rank'] = ranks.get('total', {}).get('rank', None)
        result['world_total'] = ranks.get('total', {}).get('team_count', None)
        result['district_rank'] = ranks.get('district', {}).get('rank', None)
        result['district_total'] = ranks.get('district', {}).get('team_count', None)
        
    except Exception as e:
        print(f"Error getting team info: {e}", file=sys.stderr)
    
    return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Team number required"}))
        sys.exit(1)
    
    team_num = int(sys.argv[1])
    year = int(sys.argv[2]) if len(sys.argv) > 2 else 2025
    
    info = get_team_info(team_num, year)
    print(json.dumps(info))