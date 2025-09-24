from flask import Flask, render_template_string
import sqlite3

app = Flask(__name__)

@app.route('/')
def show_all_tables():
    conn = sqlite3.connect('instance/food_platform.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    tables = [
        ("User", ["id", "email", "password_hash", "name", "user_type", "address", "purpose"]),
        ("Listing", ["id", "donor_id", "food_type", "quantity", "description", "best_before", "address"]),
        ("Request", ["id", "listing_id", "ngo_id", "status"])
    ]

    tables_data = []
    for table, columns in tables:
        try:
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            tables_data.append({
                'name': table,
                'columns': columns,
                'rows': rows,
            })
        except sqlite3.Error as e:
            tables_data.append({
                'name': table,
                'columns': columns,
                'rows': [],
                'error': str(e)
            })

    conn.close()

    html = """
    <html>
    <head>
        <title>All Tables in food_platform.db</title>
        <style>
            body { font-family: Arial, sans-serif; background: #fafcfb; }
            table { border-collapse: collapse; margin: 20px 0; }
            th, td { border: 1px solid #888; padding: 5px 12px; }
            th { background: #e8f5e9; }
            h2 { color: #388e3c; }
            .error { color: #f57c00; padding: 8px; }
        </style>
    </head>
    <body>
        <h1>All Tables in food_platform.db</h1>
        {% for tbl in tables_data %}
            <h2>{{ tbl.name }}</h2>
            {% if tbl.error %}
                <div class="error">Error: {{ tbl.error }}</div>
            {% else %}
            <table>
                <tr>
                    {% for col in tbl.columns %}
                        <th>{{ col }}</th>
                    {% endfor %}
                </tr>
                {% for row in tbl.rows %}
                    <tr>
                        {% for col in tbl.columns %}
                            <td>{{ row[col] }}</td>
                        {% endfor %}
                    </tr>
                {% endfor %}
            </table>
            {% endif %}
        {% endfor %}
    </body>
    </html>
    """
    return render_template_string(html, tables_data=tables_data)

if __name__ == '__main__':
    app.run(debug=True)