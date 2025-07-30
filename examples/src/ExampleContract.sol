// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

import "forge-std/Test.sol";
import "forge-std/console.sol";
import "./Counter.sol";

contract ExampleContract is Test {
    Counter public counter;
    
    function setUp() public {
        counter = new Counter();
    }
    
    function testIncrement() public {
        counter.increment();
        assertEq(counter.number(), 1);
        console.log("Counter value:", counter.number());
    }
    
    function testSetNumber() public {
        counter.setNumber(42);
        assertEq(counter.number(), 42);
    }
}