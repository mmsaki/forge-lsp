// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

contract TestMonitoring {
    uint256 public value;
    
    function setValue(uint256 _value) public {
        value = _value;
        // This will be the error we fix
        undefinedVar = 10;
    }
    
    function getValue() public view returns (uint256) {
        return value;
    }
}