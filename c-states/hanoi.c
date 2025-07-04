int count = 0;

void hanoi(int n, char from, char to, char via) {
    if (n == 1) {
        count++;
    } else {
        hanoi(n - 1, from, via, to);
        hanoi(1, from, to, via);
        hanoi(n - 1, via, to, from);
    }
}

int main() {
    hanoi(2, 'A', 'C', 'B');
}
