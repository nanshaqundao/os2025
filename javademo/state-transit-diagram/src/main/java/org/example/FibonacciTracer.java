package org.example;

import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.List;

/**
 * 不使用JDI的斐波那契状态跟踪工具
 * 这个版本使用自定义的跟踪方法直接插入到斐波那契计算中
 */
public class FibonacciTracer {

    // 记录所有函数调用状态
    private static final List<StateNode> stateNodes = new ArrayList<>();
    // 状态节点ID计数器
    private static int nodeCounter = 0;
    // 当前调用栈
    private static final List<StateNode> callStack = new ArrayList<>();

    public static void main(String[] args) {
        if (args.length < 1) {
            System.out.println("Usage: java org.example.FibonacciTracer <n>");
            return;
        }

        int n = Integer.parseInt(args[0]);
        System.out.println("开始计算并跟踪斐波那契数列 n = " + n);

        // 计算斐波那契数
        int result = tracedFibonacci(n);

        System.out.println("计算结果 fibonacci(" + n + ") = " + result);
        System.out.println("总共记录了 " + stateNodes.size() + " 个状态节点");

        // 生成状态图
        generateDotGraph("fibonacci_" + n + "_state_graph.dot");
        System.out.println("已生成状态图: fibonacci_" + n + "_state_graph.dot");
    }

    /**
     * 带跟踪的斐波那契函数计算
     */
    public static int tracedFibonacci(int n) {
        // 创建当前函数调用的状态节点
        StateNode currentNode = new StateNode(nodeCounter++, "fibonacci", n);
        stateNodes.add(currentNode);

        // 如果调用栈不为空，建立父子关系
        if (!callStack.isEmpty()) {
            StateNode parent = callStack.get(callStack.size() - 1);
            parent.addChild(currentNode);
        }

        // 将当前节点压入调用栈
        callStack.add(currentNode);

        // 执行实际的斐波那契计算
        int result;
        if (n <= 1) {
            result = n;
        } else {
            // 递归调用，同时跟踪状态
            int leftResult = tracedFibonacci(n - 1);
            int rightResult = tracedFibonacci(n - 2);
            result = leftResult + rightResult;
        }

        // 记录返回值
        currentNode.setReturnValue(result);

        // 从调用栈中弹出当前节点
        callStack.remove(callStack.size() - 1);

        return result;
    }

    /**
     * 生成DOT格式的状态图
     */
    private static void generateDotGraph(String fileName) {
        try (PrintWriter writer = new PrintWriter(new FileWriter(fileName))) {
            writer.println("digraph FibonacciStates {");
            writer.println("  rankdir=LR;");
            writer.println("  node [shape=box, style=filled, fillcolor=lightblue];");

            // 输出所有节点
            for (StateNode node : stateNodes) {
                writer.println("  node" + node.getId() + " [label=\"fibonacci(" +
                        node.getParamValue() + ")\\nreturn " + node.getReturnValue() + "\"];");
            }

            // 输出所有边
            for (StateNode node : stateNodes) {
                for (StateNode child : node.getChildren()) {
                    writer.println("  node" + node.getId() + " -> node" + child.getId() + ";");
                }
            }

            writer.println("}");
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    /**
     * 表示函数调用的状态节点
     */
    static class StateNode {
        private final int id;
        private final String methodName;
        private final int paramValue;
        private int returnValue;
        private final List<StateNode> children = new ArrayList<>();

        public StateNode(int id, String methodName, int paramValue) {
            this.id = id;
            this.methodName = methodName;
            this.paramValue = paramValue;
            this.returnValue = -1; // 初始为-1表示尚未返回
        }

        public int getId() {
            return id;
        }

        public String getMethodName() {
            return methodName;
        }

        public int getParamValue() {
            return paramValue;
        }

        public int getReturnValue() {
            return returnValue;
        }

        public void setReturnValue(int returnValue) {
            this.returnValue = returnValue;
        }

        public void addChild(StateNode child) {
            children.add(child);
        }

        public List<StateNode> getChildren() {
            return children;
        }
    }
}