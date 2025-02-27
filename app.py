# # app.py
# from flask import Flask, render_template, request, jsonify
# from datetime import datetime, timedelta
# import os
# import requests
# from dotenv import load_dotenv

# load_dotenv()

# app = Flask(__name__)

# preferences_store = {
#     "beer_threshold": 50,
#     "consumption_rate": 5,
#     "state": "Maharashtra"
# }

# def get_state_dry_days(state):
#     today = datetime.today()
#     try:
#         response = requests.get(
#             "https://calendarific.com/api/v2/holidays",
#             params={
#                 'api_key': os.getenv('CALENDARIFIC_API_KEY'),
#                 'country': 'IN',
#                 'year': today.year,
#                 'type': 'national',
#                 'location': state
#             }
#         )
#         holidays = response.json().get('response', {}).get('holidays', [])
#         return {
#             'dry_days': [datetime.strptime(h['date']['iso'], "%Y-%m-%dT%H:%M:%S%z").date()
#                         for h in holidays if h.get('type') == 'National holiday'],
#             'state': state
#         }
#     except:
#         state_dry_days = {
#             'Maharashtra': [datetime(today.year, 5, 1).date()],
#             'Delhi': [datetime(today.year, 2, 16).date()],
#             'Karnataka': [datetime(today.year, 11, 1).date()]
#         }
#         return {
#             'dry_days': state_dry_days.get(state, []),
#             'state': state
#         }

# def calculate_restock_days(beer_threshold, consumption_rate, dry_days):
#     today = datetime.today().date()
#     if consumption_rate == 0:
#         return []
    
#     days_remaining = beer_threshold / consumption_rate
#     critical_date = today + timedelta(days=days_remaining)
    
#     restock_days = []
#     for dry_day in [d for d in dry_days if d > today]:
#         if dry_day < critical_date:
#             suggestion = dry_day - timedelta(days=1)
#             if suggestion > today:
#                 restock_days.append(suggestion)
    
#     if not restock_days and critical_date > today:
#         restock_days.append(critical_date)
    
#     return restock_days

# @app.route('/')
# def index():
#     return render_template('index.html')

# @app.route('/api/preferences', methods=['POST'])
# def save_preferences():
#     data = request.json
#     preferences_store.update({
#         "beer_threshold": data['beerThreshold'],
#         "consumption_rate": data['consumptionRate'],
#         "state": data['state']
#     })
#     return jsonify({'status': 'success'})

# @app.route('/api/suggestions')
# def get_suggestion():
#     state_data = get_state_dry_days(preferences_store['state'])
#     restock_days = calculate_restock_days(
#         preferences_store['beer_threshold'],
#         preferences_store['consumption_rate'],
#         state_data['dry_days']
#     )
    
#     next_restock = restock_days[0].strftime('%b %d, %Y') if restock_days else "No restock needed"
    
#     return jsonify({
#         'suggestion': next_restock,
#         'restock_days': [d.strftime('%Y-%m-%d') for d in restock_days],
#         'dry_days': [d.strftime('%Y-%m-%d') for d in state_data['dry_days']]
#     })

# if __name__ == '__main__':
#     app.run(debug=True)



from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import os
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

preferences_store = {
    "beer_threshold": 50,
    "consumption_rate": 5,
    "state": "Maharashtra"
}

def parse_holiday_date(date_str):
    """Try to parse the date using multiple formats."""
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Date string {date_str} does not match expected formats.")

def get_state_dry_days(state):
    today = datetime.today()
    api_key = os.getenv('CALENDARIFIC_API_KEY')
    if not api_key:
        print("No Calendarific API key provided, using fallback dates.")
        return [
            today.replace(day=1).date(),
            today.replace(day=15).date(),
            today.replace(day=25).date()
        ]
    try:
        response = requests.get(
            "https://calendarific.com/api/v2/holidays",
            params={
                'api_key': api_key,
                'country': 'IN',
                'year': today.year,
                'type': 'national',
                'location': state
            },
            timeout=5
        )

        holidays = response.json().get('response', {}).get('holidays', [])
        return [
            parse_holiday_date(h['date']['iso'])
            for h in holidays 
            if ('National holiday' in h.get('type', [])) or (h.get('type') == 'National holiday')
        ]
    except Exception as e:
        print(f"Calendar API Error: {str(e)}")
        return [
            today.replace(day=1).date(),
            today.replace(day=15).date(),
            today.replace(day=25).date()
        ]


def calculate_restock_days(beer_threshold, consumption_rate, dry_days):
    today = datetime.today().date()
    if consumption_rate <= 0:
        return []
    
    days_remaining = beer_threshold / consumption_rate
    critical_date = today + timedelta(days=days_remaining)
    
    restock_days = []
    for dry_day in sorted([d for d in dry_days if d > today]):
        if dry_day <= critical_date:
            restock_day = dry_day - timedelta(days=1)
            if restock_day > today:
                restock_days.append(restock_day)
        else:
            break
    
    if not restock_days and critical_date > today:
        restock_days.append(critical_date)
    
    return restock_days[:3]

def get_llm_explanation(state, dry_days, restock_days, beer_threshold, consumption_rate):
    prompt = f"""As a supply chain expert with beer industry experience, explain in 3 concise sentences with emojis:
    - Why these restock dates are chosen for {state}
    - Dry days: {dry_days}
    - Recommended restock dates: {restock_days}
    - Current threshold: {beer_threshold} units
    - Consumption rate: {consumption_rate}/day
    Make it friendly and practical:all this in json format strictly  """
    
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        print("No GROQ API key provided, using fallback explanation.")
        return "🔍 AI insights temporarily unavailable. Our team is working on it!"
    try:
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                "model": "llama3-70b-8192",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 200
            },
            timeout=5
        )
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"LLM Error: {str(e)}")
        return "🔍 AI insights temporarily unavailable. Our team is working on it!"


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/preferences', methods=['POST'])
def save_preferences():
    data = request.json
    preferences_store.update(data)
    return jsonify({'status': 'success'})

@app.route('/api/suggestions')
def get_suggestion():
    try:
        state = preferences_store['state']
        dry_days = get_state_dry_days(state)
        restock_days = calculate_restock_days(
            preferences_store['beer_threshold'],
            preferences_store['consumption_rate'],
            dry_days
        )
        
        llm_explanation = get_llm_explanation(
            state,
            [d.strftime('%Y-%m-%d') for d in dry_days],
            [d.strftime('%Y-%m-%d') for d in restock_days],
            preferences_store['beer_threshold'],
            preferences_store['consumption_rate']
        )

        next_restock = restock_days[0].strftime('%b %d, %Y') if restock_days else "No restock needed"
        
        return jsonify({
            'dryDays': [d.strftime('%Y-%m-%d') for d in dry_days],
            'restockDays': [d.strftime('%Y-%m-%d') for d in restock_days],
            'state': state,
            'nextRestock': next_restock,
            'llmExplanation': llm_explanation
        })
    except Exception as e:
        print("Error in suggestions endpoint:", e)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)

