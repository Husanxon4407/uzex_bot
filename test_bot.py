# Asks the bot every question from test_questions.txt (no Telegram) and shows answer + time.
# Usage: python test_bot.py            -> all questions
#        python test_bot.py 4 10       -> only questions 4 and 10
import sys, time
from bot import answer

questions = [line.split("<-")[0].strip()
             for line in open("test_questions.txt", encoding="utf-8")
             if line.strip() and not line.startswith("#")]
pick = [int(a) for a in sys.argv[1:]] or range(1, len(questions) + 1)

for n in pick:
    q = questions[n - 1]
    t = time.time()
    text, sql = answer(q)
    print(f"\n========== Q{n} ({time.time() - t:.1f} s): {q}\n{text}\n\n--- SQL ---\n{sql}")
    time.sleep(4)                      # be gentle with the free-tier per-minute limit
