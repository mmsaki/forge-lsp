// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

contract TestLint {
    uint256 public value;
    uint256 private unusedVar; // This should trigger a lint warning
    uint256 constant constantValue = 100; // Should be SCREAMING_SNAKE_CASE
    
    function setValue(uint256 _value) public {
        value = _value;
        uint256 localUnused = 42; // Unused local variable
    }
    
    function badNaming() public pure returns (uint256) {
        return 1;
    }
    
    // Function with gas inefficiency
    function inefficientLoop() public pure returns (uint256) {
        uint256 sum = 0;
        for (uint256 i = 0; i < 1000; i++) {
            sum += i;
        }
        return sum;
    }
}
