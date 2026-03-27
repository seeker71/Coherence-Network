"""Simple number guessing game."""
import random

def play():
    target = random.randint(1, 100)
    print("Guess a number between 1 and 100")
    guesses = 0
    while True:
        try:
            guess = int(input("Your guess: "))
        except ValueError:
            print("Please enter a valid integer.")
            continue
        guesses += 1
        if guess < target:
            print("Higher!")
        elif guess > target:
            print("Lower!")
        else:
            print(f"Correct! You got it in {guesses} guess{'es' if guesses != 1 else ''}.")
            score = max(0, 100 - (guesses - 1) * 10)
            print(f"Score: {score}")
            break

if __name__ == "__main__":
    play()
