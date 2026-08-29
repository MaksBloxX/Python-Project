print("---------- Simple Calculator ----------\n")

while True:
    num1 = float(input("Enter First Number : "))
    num2 = float(input("Enter Second Number: "))

    print("\nChoose Operation")
    print("1. Addition")
    print("2. Subtraction")
    print("3. Multiplication")
    print("4. Division")

    choice = int(input("\nEnter Choice (1-4): "))

    if choice == 1:
        result = num1 + num2
        operation = "+"

    elif choice == 2:
        result = num1 - num2
        operation = "-"

    elif choice == 3:
        result = num1 * num2
        operation = "*"

    elif choice == 4:
        if num2 != 0:
            result = num1 / num2
            operation = "/"
        else:
            print("\nCannot divide by zero!")
            continue

    else:
        print("\nInvalid Choice!")
        continue

    integer_result = int(result)

    print("\n---------- Result ----------")
    print(f"{num1} {operation} {num2} = {result:.2f}")
    print("\nAfter Typecasting to Integer result =", integer_result)
   
    again = input("\nDo you want another calculation? (yes/no): ")

    if again.lower() != "yes":
        print("\nCalculator Closed.")
        break