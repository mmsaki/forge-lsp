// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {Test, console} from "forge-std/Test.sol";
import {A} from "../A.sol";

contract ATest is Test {
    A public a;

    function setUp() public {
        a = new A();
    }
}
