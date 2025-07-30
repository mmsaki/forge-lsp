// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

contract TestErrors {
    uint256 public value;
    
    function setValue(uint256 _value) public {
        value = _value;
        // Undefined variable
        undefinedVar = 10;
    }
    
    // Wrong return type
    function getValue() public view returns (string memory) {
        return value; // Should return uint256, not string
    }
}