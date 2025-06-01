from flask import Flask, render_template, request, redirect, url_for, send_file
import os
import pandas as pd

app = Flask(__name__)
app.secret_key = 'YourSecretKey'

DATA_FILE = 'data.csv'

FIELDS = ['Test No.', 'Date', 'Q No.', 'Chapter', 'Attempted', 'Correct', 'Difficulty', 'Remarks']
CHAPTERS = [
    "Data Interpretation", "Algebra", "Average", "Co-ordinate Geometry", "Geometry(Circles)",
    "Geometry(Triangles)", "Mensuration", "Geometry", "SI/CI", "Time,Speed&Distance",
    "Mixtures&Alligations", "Ratio&Porportions", "Simplification", "Boats&Streams", "Time&Work",
    "Trignometry", "Heights&Distances", "Number System", "Percentages,Profit &Loss", "Pipes & Cisterns"
]
DIFFICULTY_LEVELS = ['Easy', 'Medium', 'Hard']
REMARKS_OPTIONS = ['Silly mistake', 'Analytical', 'Skipped']

CHAPTER_KEYWORDS = {
    "Data Interpretation": ["data", "interpretation"],
    "Algebra": ["algebra"],
    "Average": ["average"],
    "Co-ordinate Geometry": ["co-ordinate", "coordinate", "co ordinate"],
    "Geometry(Circles)": ["geometry(circles)", "circle"],
    "Geometry(Triangles)": ["geometry(triangles)", "triangle"],
    "Mensuration": ["mensuration"],
    "Geometry": ["geometry"],
    "SI/CI": ["si", "ci", "compound", "interest"],
    "Time,Speed&Distance": ["time", "speed", "distance"],
    "Mixtures&Alligations": ["mixture", "alligation"],
    "Ratio&Porportions": ["ratio", "proportion"],
    "Simplification": ["simplification"],
    "Boats&Streams": ["boat", "stream"],
    "Time&Work": ["time", "work"],
    "Trignometry": ["trigno", "trig"],
    "Heights&Distances": ["height", "distance"],
    "Number System": ["number system"],
    "Percentages,Profit &Loss": ["percent", "profit", "loss"],
    "Pipes & Cisterns": ["pipe", "cistern"]
}

def match_chapter(value):
    val = str(value).strip().lower()
    for canonical, keywords in CHAPTER_KEYWORDS.items():
        for keyword in keywords:
            if keyword in val:
                return canonical
    return val.title()

def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    return pd.DataFrame(columns=FIELDS)

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

@app.route('/', methods=['GET', 'POST'])
def add_entry():
    if request.method == 'POST':
        try:
            new_entry = {
                'Test No.': int(request.form['test_no']),
                'Date': request.form['date'],
                'Q No.': int(request.form['q_no']),
                'Chapter': match_chapter(request.form['chapter']),
                'Attempted': request.form['attempted'],
                'Correct': request.form['correct'],
                'Difficulty': request.form['difficulty'],
                'Remarks': request.form['remarks']
            }

            # Validation
            assert new_entry['Test No.'] >= 1
            assert 1 <= new_entry['Q No.'] <= 25
            assert new_entry['Chapter'] in CHAPTERS
            assert new_entry['Attempted'] in ['Yes', 'No']
            assert new_entry['Correct'] in ['Yes', 'No']
            assert new_entry['Difficulty'] in DIFFICULTY_LEVELS
            assert new_entry['Remarks'] in REMARKS_OPTIONS

            df = load_data()
            df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
            save_data(df)
            return redirect(url_for('add_entry'))

        except Exception as e:
            return f"Error in input: {str(e)}", 400

    return render_template('add.html', chapters=CHAPTERS, difficulties=DIFFICULTY_LEVELS, remarks=REMARKS_OPTIONS)

@app.route('/records')
def view_records():
    df = load_data()
    test_no = request.args.get('test_no')

    if df.empty:
        return "<h3>No records found.</h3><a href='/'>Go Back</a>"

    if test_no:
        try:
            test_no = int(test_no)
            df = df[df['Test No.'] == test_no]
        except ValueError:
            pass

    return render_template('records.html', records=df.to_dict(orient='records'), test_no=test_no or "")

@app.route('/import', methods=['POST'])
def import_data():
    file = request.files.get('file')
    if not file:
        return "No file uploaded", 400

    try:
        if file.filename.endswith('.xlsx'):
            df_new = pd.read_excel(file, dtype=str)
        elif file.filename.endswith('.csv'):
            df_new = pd.read_csv(file, dtype=str)
        else:
            return "Unsupported file format. Upload a .csv or .xlsx file.", 400

        df_cols_norm = {col.strip().lower(): col for col in df_new.columns}

        COLUMN_ALIASES = {
            'Test No.': ['test no', 'test number', 'test_no','Test No.'],
            'Date': ['date'],
            'Q No.': ['q no', 'question number', 'q#','Q No.'],
            'Chapter': ['chapter', 'topic'],
            'Attempted': ['attempted', 'attempt status'],
            'Correct': ['correct', 'correct answer', 'is correct'],
            'Difficulty': ['difficulty', 'level'],
            'Remarks': ['remarks', 'comment', 'note']
        }

        col_map = {}
        missing = []
        for required_col, aliases in COLUMN_ALIASES.items():
            for alias in aliases:
                key = alias.strip().lower()
                if key in df_cols_norm:
                    col_map[df_cols_norm[key]] = required_col
                    break
            else:
                missing.append(required_col)

        if missing:
            return f"Missing columns in uploaded file: {missing}", 400

        df_renamed = df_new.rename(columns=col_map)

        if 'Chapter' in df_renamed.columns:
            df_renamed['Chapter'] = df_renamed['Chapter'].apply(match_chapter)

        df_final = df_renamed[[col for col in FIELDS if col in df_renamed.columns]]

        if 'Date' in df_final.columns:
            df_final['Date'] = pd.to_datetime(df_final['Date'], errors='coerce').dt.date.astype(str)

        df_existing = load_data()
        df_combined = pd.concat([df_existing, df_final], ignore_index=True)

        save_data(df_combined)
        return redirect(url_for('view_records'))

    except Exception as e:
        return f"Import error: {str(e)}", 500

@app.route('/export')
def export_data():
    if not os.path.exists(DATA_FILE):
        return "No data to export", 404
    return send_file(DATA_FILE, as_attachment=True)

@app.route('/statistics')
def statistics():
    df = load_data()
    if df.empty:
        return "<h3>No records found to compute statistics.</h3><a href='/'>Go Back</a>"

    df['Chapter'] = df['Chapter'].apply(match_chapter)

    stats = []
    total_questions_all = len(df)

    for chapter in df['Chapter'].dropna().unique():
        df_chap = df[df['Chapter'] == chapter]

        total = len(df_chap)
        attempted = len(df_chap[df_chap['Attempted'] == 'Yes'])
        correct = len(df_chap[df_chap['Correct'] == 'Yes'])
        incorrect = len(df_chap[df_chap['Correct'] == 'No'])
        unattempted = len(df_chap[df_chap['Attempted'] == 'No'])

        accuracy = round((correct / attempted * 100), 2) if attempted > 0 else 0
        score = (2 * correct) - (5 * incorrect)
        score_pct = round((score / (total * 2) * 100), 2) if total > 0 else 0
        unattempted_rate = round((unattempted / total * 100), 2) if total > 0 else 0

        skipped_total = len(df_chap[(df_chap['Remarks'] == 'Skipped') & (df_chap['Attempted'] == 'No')])
        skipped_pct = round((skipped_total / unattempted * 100), 2) if unattempted > 0 else 0

        topic_pct = round((total / total_questions_all * 100), 2) if total_questions_all > 0 else 0

        stats.append({
            'Chapter': chapter,
            'Total Questions': total,
            'Attempted': attempted,
            'Correct': correct,
            'Incorrect': incorrect,
            'Accuracy (%)': accuracy,
            'Score': score,
            'Score Percentage(%)': score_pct,
            'Unattempted': unattempted,
            'Unattempted Rate (%)': unattempted_rate,
            'Skipped (Total) %': skipped_pct,
            'Topic %': topic_pct
        })

    return render_template('statistics.html', stats=stats)

if __name__ == '__main__':
    app.run(debug=True)
