package org.example;

public class Fibonacci {
    public static void main(String[] args) {
        if (args.length < 1) {
            System.out.println("Usage: java org.example.Fibonacci <n>");
            return;
        }

        int n = Integer.parseInt(args[0]);
        int result = fibonacci(n);
        System.out.println("Fibonacci(" + n + ") = " + result);
    }

    public static int fibonacci(int n) {
        if (n <= 1) {
            return n;
        }
        return fibonacci(n-1) + fibonacci(n-2);
    }
}